"""
Funnel Tracking Dashboard - Webhook Receiver & Server
=====================================================
Receives POST requests from Zapier, stores data in PostgreSQL,
and serves the dashboard.

PERSISTENT STORAGE: Uses PostgreSQL (DATABASE_URL env var).
Data survives Render redeployments.

ZAPIER WEBHOOK URL:  http://<your-server>/webhook

PAYLOAD FORMAT (send as JSON from Zapier's "Webhooks by Zapier" action):

  {
    "timeframe": "daily",       // "daily" | "weekly" | "monthly"
    "category": "ads",          // "ads" | "funnel" | "sales" | "closers" | "setters"
    "data": { ... }             // the metric values to merge in
  }

For closers/setters, include a "name" field in data to identify the person.

Optional: add "auth_token" to the payload if you set AUTH_TOKEN below.

RUN:
  python3 app.py
"""

import json
import os
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory

# ============================================================
# CONFIG
# ============================================================
WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(WORKSPACE, "dashboard_data.json")
PORT = int(os.environ.get("PORT", 5000))
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Set an auth token to prevent random POSTs. Leave empty to disable.
AUTH_TOKEN = ""

# ============================================================
# DATABASE SETUP
# ============================================================
_db_conn = None

def get_db():
    """Get a database connection (creates one if needed)."""
    global _db_conn
    if not DATABASE_URL:
        return None
    if _db_conn is None or _db_conn.closed:
        import psycopg2
        # Supabase and most cloud DBs require SSL
        conn_kwargs = {"sslmode": "require"}
        _db_conn = psycopg2.connect(DATABASE_URL, **conn_kwargs)
        _db_conn.autocommit = True
    return _db_conn


def init_db():
    """Create the dashboard_data table if it doesn't exist."""
    if not DATABASE_URL:
        return
    conn = get_db()
    if not conn:
        return
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dashboard_data (
            id SERIAL PRIMARY KEY,
            data JSONB NOT NULL,
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    # Check if we have any data, if not seed from the JSON file
    cur.execute("SELECT COUNT(*) FROM dashboard_data;")
    count = cur.fetchone()[0]
    if count == 0:
        # Seed from local JSON file if it exists
        seed = load_data_file()
        cur.execute(
            "INSERT INTO dashboard_data (data) VALUES (%s);",
            (json.dumps(seed),)
        )
    cur.close()


def load_data_db():
    """Load dashboard data from PostgreSQL."""
    conn = get_db()
    if not conn:
        return load_data_file()
    cur = conn.cursor()
    cur.execute("SELECT data FROM dashboard_data ORDER BY id DESC LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    if row:
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    return {}


def save_data_db(data):
    """Save dashboard data to PostgreSQL."""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    if not conn:
        save_data_file(data)
        return
    cur = conn.cursor()
    # Upsert: update the single row if it exists, otherwise insert
    cur.execute("SELECT COUNT(*) FROM dashboard_data;")
    count = cur.fetchone()[0]
    if count > 0:
        cur.execute(
            "UPDATE dashboard_data SET data = %s, updated_at = NOW() WHERE id = (SELECT id FROM dashboard_data ORDER BY id DESC LIMIT 1);",
            (json.dumps(data),)
        )
    else:
        cur.execute(
            "INSERT INTO dashboard_data (data) VALUES (%s);",
            (json.dumps(data),)
        )
    cur.close()


# ============================================================
# FILE FALLBACK (for local dev / no database)
# ============================================================
def load_data_file():
    """Load the current dashboard data from JSON file (fallback)."""
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_data_file(data):
    """Save dashboard data to JSON file (fallback)."""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ============================================================
# UNIFIED LOAD/SAVE (auto-detects DB vs file)
# ============================================================
def load_data():
    """Load data from DB if available, otherwise from file."""
    if DATABASE_URL:
        try:
            return load_data_db()
        except Exception as e:
            print(f"  [DB ERROR] load_data failed, falling back to file: {e}")
            return load_data_file()
    return load_data_file()


def save_data(data):
    """Save data to DB if available, otherwise to file."""
    if DATABASE_URL:
        try:
            save_data_db(data)
            return
        except Exception as e:
            print(f"  [DB ERROR] save_data failed, falling back to file: {e}")
    save_data_file(data)


# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__, static_folder=WORKSPACE)


def deep_merge(base, update):
    """Recursively merge update dict into base dict."""
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def check_auth(payload):
    """Check if auth token is valid (if configured)."""
    if not AUTH_TOKEN:
        return True
    return payload.get("auth_token") == AUTH_TOKEN


# ============================================================
# ROUTES - DASHBOARD
# ============================================================
@app.route("/")
def dashboard():
    return send_from_directory(WORKSPACE, "dashboard.html")


@app.route("/dashboard_data.json")
def data_endpoint():
    return jsonify(load_data())


# ============================================================
# ROUTES - WEBHOOK RECEIVER
# ============================================================
@app.route("/webhook", methods=["POST"])
def receive_webhook():
    """Receive data from Zapier and update the dashboard."""
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload:
            return jsonify({"status": "error", "message": "No JSON body received"}), 400

        if not check_auth(payload):
            return jsonify({"status": "error", "message": "Invalid auth token"}), 401

        timeframe = payload.get("timeframe", "daily").lower()
        category = payload.get("category", "").lower()
        data = payload.get("data", {})

        if timeframe not in ("daily", "weekly", "monthly"):
            return jsonify({"status": "error", "message": f"Invalid timeframe: {timeframe}"}), 400

        if category not in ("ads", "funnel", "sales", "closers", "setters"):
            return jsonify({"status": "error", "message": f"Invalid category: {category}"}), 400

        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        # Load current data
        dashboard_data = load_data()

        # Handle closers and setters (list-based, not dict merge)
        if category in ("closers", "setters"):
            person_name = data.get("name", "").strip()
            if not person_name:
                return jsonify({"status": "error", "message": "Closers/setters require a 'name' field"}), 400

            people_list = dashboard_data.get(timeframe, {}).get(category, [])
            if not isinstance(people_list, list):
                people_list = []

            # Find existing person or create new entry
            existing = None
            for p in people_list:
                if p.get("name", "").lower() == person_name.lower():
                    existing = p
                    break

            if existing:
                deep_merge(existing, data)
            else:
                people_list.append(data)

            dashboard_data.setdefault(timeframe, {})[category] = people_list

        else:
            # Handle ads, funnel, sales (dict merge)
            if timeframe not in dashboard_data:
                dashboard_data[timeframe] = {}

            if category not in dashboard_data[timeframe]:
                dashboard_data[timeframe][category] = {}

            deep_merge(dashboard_data[timeframe][category], data)

        # Recalculate keystone metrics if we have the inputs
        recalculate_keystones(dashboard_data)
        recalculate_derived_metrics(dashboard_data)

        # Save
        save_data(dashboard_data)

        return jsonify({
            "status": "success",
            "message": f"Updated {timeframe}.{category}",
            "last_updated": dashboard_data.get("last_updated", "")
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/webhook/reset", methods=["POST"])
def reset_data():
    """Reset all data to zeros. Useful for start of new day/week/month."""
    try:
        payload = request.get_json(force=True, silent=True) or {}
        if not check_auth(payload):
            return jsonify({"status": "error", "message": "Invalid auth token"}), 401

        timeframe = payload.get("timeframe", "all").lower()

        dashboard_data = load_data()

        if timeframe == "all":
            for tf in ("daily", "weekly", "monthly"):
                reset_timeframe(dashboard_data, tf)
            dashboard_data["eod_entries"] = []
        elif timeframe in ("daily", "weekly", "monthly"):
            reset_timeframe(dashboard_data, timeframe)
        else:
            return jsonify({"status": "error", "message": "Invalid timeframe"}), 400

        save_data(dashboard_data)
        return jsonify({"status": "success", "message": f"Reset {timeframe} data"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/eod/clear", methods=["POST"])
def clear_eod():
    """Clear all EOD entries. Useful for removing test data."""
    try:
        dashboard_data = load_data()
        dashboard_data["eod_entries"] = []
        for tf in ("daily", "weekly", "monthly"):
            if tf in dashboard_data and "sales" in dashboard_data[tf]:
                for k in ("calls_assigned", "calls_booked", "calls_showed", "calls_closed",
                          "cash_full_pay", "cash_payment_plans", "revenue_collected", "contract_value",
                          "ad_revenue", "organic_revenue", "referral_revenue", "other_revenue",
                          "ad_calls_showed", "organic_calls_showed", "ad_calls_closed", "organic_calls_closed",
                          "show_rate", "close_rate", "aov"):
                    dashboard_data[tf]["sales"][k] = 0
            if tf in dashboard_data and "source" in dashboard_data[tf]:
                for k in dashboard_data[tf]["source"]:
                    dashboard_data[tf]["source"][k] = 0
        if "monthly" in dashboard_data:
            dashboard_data["monthly"]["closers"] = []
        recalculate_keystones(dashboard_data)
        save_data(dashboard_data)
        return jsonify({"status": "success", "message": "All EOD entries cleared"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/webhook/status", methods=["GET"])
def status():
    """Health check endpoint."""
    data = load_data()
    db_test = "not_configured"
    if DATABASE_URL:
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT 1;")
            cur.close()
            db_test = "connected"
        except Exception as e:
            db_test = f"error: {str(e)}"
    return jsonify({
        "status": "online",
        "last_updated": data.get("last_updated", "never"),
        "storage": "postgresql" if DATABASE_URL else "file",
        "database_connected": bool(DATABASE_URL),
        "db_test": db_test
    }), 200


# ============================================================
# ROUTES - EOD (END OF DAY) CLOSER REPORT FORM
# ============================================================
EOD_FORM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EOD Report - Closer Form</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0a0a0a;color:#fff;padding:20px;max-width:600px;margin:0 auto}
h1{text-align:center;font-size:24px;margin-bottom:8px;color:#fff}
.sub{text-align:center;color:#888;font-size:14px;margin-bottom:24px}
.field{margin-bottom:16px}
label{display:block;font-size:13px;color:#aaa;margin-bottom:6px;font-weight:600}
input,select,textarea{width:100%;padding:12px;border-radius:8px;border:1px solid #333;background:#111;color:#fff;font-size:16px}
input:focus,select:focus,textarea:focus{outline:none;border-color:#3b82f6}
.btn{width:100%;padding:16px;border:none;border-radius:10px;background:#3b82f6;color:#fff;font-size:18px;font-weight:700;cursor:pointer;margin-top:12px}
.btn:hover{background:#2563eb}
.btn:active{transform:scale(0.98)}
.success{display:none;text-align:center;padding:40px 20px}
.success h2{color:#22c55e;font-size:28px;margin-bottom:12px}
.success p{color:#888;font-size:16px}
.row{display:flex;gap:12px}
.row .field{flex:1}
@media(max-width:480px){.row{flex-direction:column;gap:0}}
</style>
</head>
<body>
<h1>Daily EOD Report</h1>
<p class="sub">Fill this out at the end of each day</p>

<div id="form-wrap">
<form id="eodForm">

<div class="field">
<label>Closer Name *</label>
<input type="text" name="closer_name" placeholder="Your name" required>
</div>

<div class="field">
<label>Date *</label>
<input type="date" name="date" required id="dateField">
</div>

<div class="row">
<div class="field">
<label>Lead Source *</label>
<select name="source" required>
<option value="">-- Select --</option>
<option value="ads">Ads (Paid Traffic)</option>
<option value="organic">Organic</option>
<option value="referral">Referral</option>
<option value="other">Other</option>
</select>
</div>
<div class="field">
<label>Calls Assigned</label>
<input type="number" name="calls_assigned" placeholder="0" min="0" value="0">
</div>
</div>

<div class="row">
<div class="field">
<label>Calls Showed Up *</label>
<input type="number" name="calls_showed" placeholder="0" min="0" value="0" required>
</div>
<div class="field">
<label>Calls Closed *</label>
<input type="number" name="calls_closed" placeholder="0" min="0" value="0" required>
</div>
</div>

<div class="field">
<label>Cash Collected - Full Pay (&pound;)</label>
<input type="number" name="cash_full_pay" placeholder="0" min="0" value="0" step="0.01">
</div>

<div class="field">
<label>Cash Collected - Payment Plans (&pound;)</label>
<input type="number" name="cash_payment_plans" placeholder="0" min="0" value="0" step="0.01">
<small style="color:#666;font-size:12px">Monthly payments received today</small>
</div>

<div class="field">
<label>Total Contract Value of Deals Closed (&pound;)</label>
<input type="number" name="contract_value" placeholder="0" min="0" value="0" step="0.01">
<small style="color:#666;font-size:12px">Full value of all deals closed today (incl payment plans)</small>
</div>

<div class="field">
<label>Notes (optional)</label>
<textarea name="notes" rows="3" placeholder="Anything worth noting..."></textarea>
</div>

<button type="submit" class="btn">Submit EOD Report</button>

</form>
</div>

<div id="successMsg" class="success">
<h2>EOD Submitted!</h2>
<p>Your report has been recorded.</p>
<p style="margin-top:20px"><button onclick="location.reload()" class="btn">Submit Another</button></p>
</div>

<script>
document.getElementById('dateField').value = new Date().toISOString().split('T')[0];

document.getElementById('eodForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const payload = {
        closer_name: formData.get('closer_name'),
        date: formData.get('date'),
        source: formData.get('source'),
        calls_assigned: parseInt(formData.get('calls_assigned') || 0),
        calls_showed: parseInt(formData.get('calls_showed') || 0),
        calls_closed: parseInt(formData.get('calls_closed') || 0),
        cash_full_pay: parseFloat(formData.get('cash_full_pay') || 0),
        cash_payment_plans: parseFloat(formData.get('cash_payment_plans') || 0),
        contract_value: parseFloat(formData.get('contract_value') || 0),
        notes: formData.get('notes') || ''
    };

    try {
        const resp = await fetch('/eod/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const result = await resp.json();
        if (result.status === 'success') {
            document.getElementById('form-wrap').style.display = 'none';
            document.getElementById('successMsg').style.display = 'block';
        } else {
            alert('Error: ' + result.message);
        }
    } catch (err) {
        alert('Error submitting: ' + err.message);
    }
});
</script>
</body>
</html>"""


@app.route("/eod")
def eod_form():
    """Serve the EOD form for closers."""
    return EOD_FORM_HTML


@app.route("/eod/submit", methods=["POST"])
def eod_submit():
    """Handle EOD form submission from closers."""
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload:
            return jsonify({"status": "error", "message": "No data received"}), 400

        closer_name = payload.get("closer_name", "").strip()
        date_str = payload.get("date", "")
        source = payload.get("source", "").strip().lower()

        if not closer_name:
            return jsonify({"status": "error", "message": "Closer name required"}), 400
        if not date_str:
            return jsonify({"status": "error", "message": "Date required"}), 400
        if source not in ("ads", "organic", "referral", "other"):
            return jsonify({"status": "error", "message": "Valid source required"}), 400

        entry = {
            "closer_name": closer_name,
            "date": date_str,
            "source": source,
            "calls_assigned": int(payload.get("calls_assigned", 0) or 0),
            "calls_showed": int(payload.get("calls_showed", 0) or 0),
            "calls_closed": int(payload.get("calls_closed", 0) or 0),
            "cash_full_pay": float(payload.get("cash_full_pay", 0) or 0),
            "cash_payment_plans": float(payload.get("cash_payment_plans", 0) or 0),
            "contract_value": float(payload.get("contract_value", 0) or 0),
            "notes": payload.get("notes", ""),
            "submitted_at": datetime.now(timezone.utc).isoformat()
        }

        dashboard_data = load_data()

        if "eod_entries" not in dashboard_data:
            dashboard_data["eod_entries"] = []

        dashboard_data["eod_entries"].append(entry)

        recalculate_eod_aggregates(dashboard_data)
        recalculate_derived_metrics(dashboard_data)
        recalculate_keystones(dashboard_data)

        save_data(dashboard_data)

        return jsonify({
            "status": "success",
            "message": f"EOD recorded for {closer_name} on {date_str}",
            "entry_count": len(dashboard_data.get("eod_entries", []))
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/eod")
def api_eod():
    """Return all EOD entries as JSON for the dashboard to consume."""
    data = load_data()
    entries = data.get("eod_entries", [])
    return jsonify({"entries": entries, "count": len(entries)}), 200


# ============================================================
# EOD AGGREGATE CALCULATIONS
# ============================================================
def recalculate_eod_aggregates(dashboard_data):
    """Aggregate all EOD entries into sales data for each timeframe."""
    entries = dashboard_data.get("eod_entries", [])
    if not entries:
        return

    from collections import defaultdict
    from datetime import datetime as dt, timedelta
    import copy

    today = dt.now(timezone.utc).date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Helper to build source + sales aggregation for a set of entries
    def aggregate(entry_list):
        result = {
            "calls_assigned": 0, "calls_booked": 0, "calls_showed": 0, "calls_closed": 0,
            "cash_full_pay": 0, "cash_payment_plans": 0, "revenue_collected": 0, "contract_value": 0,
            "ad_revenue": 0, "organic_revenue": 0, "referral_revenue": 0, "other_revenue": 0,
            "ad_calls_showed": 0, "organic_calls_showed": 0, "ad_calls_closed": 0, "organic_calls_closed": 0,
            "closer_breakdown": {},
        }
        for entry in entry_list:
            source = entry.get("source", "other")
            showed = entry.get("calls_showed", 0) or 0
            closed = entry.get("calls_closed", 0) or 0
            full_pay = entry.get("cash_full_pay", 0) or 0
            pay_plans = entry.get("cash_payment_plans", 0) or 0
            revenue = full_pay + pay_plans

            result["calls_assigned"] += entry.get("calls_assigned", 0) or 0
            result["calls_showed"] += showed
            result["calls_closed"] += closed
            result["cash_full_pay"] += full_pay
            result["cash_payment_plans"] += pay_plans
            result["revenue_collected"] += revenue
            result["contract_value"] += entry.get("contract_value", 0) or 0

            if source == "ads":
                result["ad_revenue"] += revenue
                result["ad_calls_showed"] += showed
                result["ad_calls_closed"] += closed
            elif source == "organic":
                result["organic_revenue"] += revenue
                result["organic_calls_showed"] += showed
                result["organic_calls_closed"] += closed
            elif source == "referral":
                result["referral_revenue"] += revenue
            else:
                result["other_revenue"] += revenue

            closer = entry.get("closer_name", "Unknown")
            if closer not in result["closer_breakdown"]:
                result["closer_breakdown"][closer] = {
                    "calls_showed": 0, "calls_closed": 0, "revenue": 0,
                    "cash_full_pay": 0, "cash_payment_plans": 0
                }
            result["closer_breakdown"][closer]["calls_showed"] += showed
            result["closer_breakdown"][closer]["calls_closed"] += closed
            result["closer_breakdown"][closer]["revenue"] += revenue
            result["closer_breakdown"][closer]["cash_full_pay"] += full_pay
            result["closer_breakdown"][closer]["cash_payment_plans"] += pay_plans

        result["calls_booked"] = result["calls_assigned"]
        return result

    # Filter entries by timeframe
    today_entries = [e for e in entries if e.get("date", "") == today.isoformat()]
    week_entries = []
    month_entries = []
    for e in entries:
        try:
            ed = dt.fromisoformat(e.get("date", "")).date()
        except (ValueError, TypeError):
            continue
        if ed >= week_ago:
            week_entries.append(e)
        if ed >= month_ago:
            month_entries.append(e)

    # Aggregate
    daily_agg = aggregate(today_entries)
    weekly_agg = aggregate(week_entries)
    monthly_agg = aggregate(month_entries)

    # Write sales + source into each timeframe
    for tf, agg in [("daily", daily_agg), ("weekly", weekly_agg), ("monthly", monthly_agg)]:
        if tf not in dashboard_data:
            dashboard_data[tf] = {}

        # Sales (excluding closer_breakdown)
        sales_clean = {k: v for k, v in agg.items() if k != "closer_breakdown"}
        dashboard_data[tf]["sales"] = sales_clean

        # Source breakdown
        dashboard_data[tf]["source"] = {
            "ad_revenue": agg["ad_revenue"],
            "organic_revenue": agg["organic_revenue"],
            "referral_revenue": agg["referral_revenue"],
            "other_revenue": agg["other_revenue"],
            "ad_calls_showed": agg["ad_calls_showed"],
            "organic_calls_showed": agg["organic_calls_showed"],
            "ad_calls_closed": agg["ad_calls_closed"],
            "organic_calls_closed": agg["organic_calls_closed"],
        }

    # Closer breakdown for monthly
    dashboard_data.setdefault("monthly", {})
    dashboard_data["monthly"]["closers"] = []
    for name, stats in monthly_agg["closer_breakdown"].items():
        showed = stats["calls_showed"]
        closed = stats["calls_closed"]
        revenue = stats["revenue"]
        dashboard_data["monthly"]["closers"].append({
            "name": name,
            "calls_booked": showed,
            "calls_showed": showed,
            "calls_closed": closed,
            "show_rate": round((showed / showed * 100), 2) if showed else 0,
            "close_rate": round((closed / showed * 100), 2) if showed else 0,
            "revenue_collected": revenue,
            "cash_full_pay": stats["cash_full_pay"],
            "cash_payment_plans": stats["cash_payment_plans"],
        })


# ============================================================
# KEYSTONE CALCULATIONS
# ============================================================
def safe_div(numerator, denominator):
    """Safe division returning 0 on divide-by-zero."""
    try:
        if denominator and denominator != 0:
            return round(numerator / denominator, 2)
    except (TypeError, ZeroDivisionError):
        pass
    return 0


def recalculate_keystones(dashboard_data):
    """Recalculate keystone metrics for weekly and monthly."""
    for tf in ("weekly", "monthly"):
        if tf not in dashboard_data:
            continue

        ads = dashboard_data[tf].get("ads", {})
        sales = dashboard_data[tf].get("sales", {})

        spend = ads.get("spend", 0) or 0
        leads = ads.get("leads", 0) or 0
        calls_booked = sales.get("calls_booked", 0) or 0
        calls_showed = sales.get("calls_showed", 0) or 0
        calls_closed = sales.get("calls_closed", 0) or 0
        revenue = sales.get("revenue_collected", 0) or 0

        keystone = {
            "roas": safe_div(revenue, spend),
            "cost_per_booked_call": safe_div(spend, calls_booked),
            "cost_per_showed_call": safe_div(spend, calls_showed),
            "cost_per_closed_deal": safe_div(spend, calls_closed),
            "collected_per_booked_call": safe_div(revenue, calls_booked),
            "collected_per_showed_call": safe_div(revenue, calls_showed),
        }

        dashboard_data[tf]["keystone"] = keystone


def recalculate_derived_metrics(dashboard_data):
    """Auto-calculate derived metrics (CTR, CPM, show rate, close rate, etc.) from raw inputs.
    This runs on every timeframe so Zapier only needs to send raw numbers."""
    for tf in ("daily", "weekly", "monthly"):
        if tf not in dashboard_data:
            continue

        ads = dashboard_data[tf].get("ads", {})
        funnel = dashboard_data[tf].get("funnel", {})
        sales = dashboard_data[tf].get("sales", {})

        # ADS derived metrics
        spend = ads.get("spend", 0) or 0
        impressions = ads.get("impressions", 0) or 0
        link_clicks = ads.get("link_clicks", 0) or 0
        leads = ads.get("leads", 0) or 0

        if impressions > 0:
            ads["cpm"] = round((spend / impressions) * 1000, 2)
        if impressions > 0:
            ads["link_ctr"] = round((link_clicks / impressions) * 100, 2)
        if link_clicks > 0:
            ads["cpc"] = round(spend / link_clicks, 2)
        if leads > 0:
            ads["cost_per_lead"] = round(spend / leads, 2)

        # FUNNEL derived metrics
        page_views = funnel.get("page_views", 0) or 0
        form_submissions = funnel.get("form_submissions", 0) or 0
        calls_booked_funnel = funnel.get("calls_booked", 0) or 0

        if page_views > 0:
            funnel["page_conversion_rate"] = round((form_submissions / page_views) * 100, 2)
        if form_submissions > 0:
            funnel["booking_rate"] = round((calls_booked_funnel / form_submissions) * 100, 2)

        # SALES derived metrics
        calls_booked = sales.get("calls_booked", 0) or 0
        calls_showed = sales.get("calls_showed", 0) or 0
        calls_closed = sales.get("calls_closed", 0) or 0
        revenue = sales.get("revenue_collected", 0) or 0

        if calls_booked > 0:
            sales["show_rate"] = round((calls_showed / calls_booked) * 100, 2)
        if calls_showed > 0:
            sales["close_rate"] = round((calls_closed / calls_showed) * 100, 2)
        if calls_closed > 0:
            sales["aov"] = round(revenue / calls_closed, 2)

        # CLOSER/SETTER derived metrics
        for role in ("closers", "setters"):
            people = dashboard_data[tf].get(role, [])
            if isinstance(people, list):
                for person in people:
                    p_booked = person.get("calls_booked", 0) or 0
                    p_showed = person.get("calls_showed", 0) or 0
                    p_closed = person.get("calls_closed", 0) or 0
                    p_revenue = person.get("revenue_collected", 0) or 0
                    p_outreach = person.get("outreach_sent", 0) or 0

                    if p_booked > 0:
                        person["show_rate"] = round((p_showed / p_booked) * 100, 2)
                    if p_showed > 0:
                        person["close_rate"] = round((p_closed / p_showed) * 100, 2)
                    if p_outreach > 0:
                        person["booking_rate"] = round((p_booked / p_outreach) * 100, 2)


def reset_timeframe(dashboard_data, timeframe):
    """Reset a specific timeframe to zeros."""
    zero_template = {
        "ads": {
            "spend": 0, "impressions": 0, "cpm": 0, "link_clicks": 0,
            "link_ctr": 0, "cpc": 0, "cost_per_lead": 0, "leads": 0
        },
        "funnel": {
            "page_views": 0, "form_submissions": 0, "page_conversion_rate": 0,
            "calls_booked": 0, "booking_rate": 0,
            "page_loads": 0, "visitors": 0, "plays": 0, "play_rate": 0,
            "avg_percent_watched": 0, "vsl_name": "", "vsl_version": "", "vsl_duration": 0
        },
        "sales": {
            "calls_booked": 0, "calls_showed": 0, "show_rate": 0,
            "calls_closed": 0, "close_rate": 0, "aov": 0, "revenue_collected": 0
        },
        "keystone": {
            "roas": 0, "cost_per_booked_call": 0, "cost_per_showed_call": 0,
            "cost_per_closed_deal": 0, "collected_per_booked_call": 0,
            "collected_per_showed_call": 0
        }
    }

    if timeframe in dashboard_data:
        for cat in ("ads", "funnel", "sales", "keystone"):
            if cat in zero_template:
                dashboard_data[timeframe][cat] = zero_template[cat].copy()
        if timeframe == "monthly":
            dashboard_data[timeframe]["closers"] = []
            dashboard_data[timeframe]["setters"] = []


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    # Initialize database on startup
    if DATABASE_URL:
        print("  Database: PostgreSQL (persistent)")
        init_db()
    else:
        print("  Database: File-based (NOT persistent - set DATABASE_URL for persistence)")

    print(f"")
    print(f"  Funnel Tracking Dashboard Server")
    print(f"  =================================")
    print(f"  Dashboard URL:  http://localhost:{PORT}/")
    print(f"  Webhook URL:    http://localhost:{PORT}/webhook")
    print(f"  Status URL:     http://localhost:{PORT}/webhook/status")
    print(f"  EOD Form URL:   http://localhost:{PORT}/eod")
    print(f"  Auth token:     {'enabled' if AUTH_TOKEN else 'disabled'}")
    print(f"")
    print(f"  Press Ctrl+C to stop")
    print(f"")

    app.run(host="0.0.0.0", port=PORT, debug=False)