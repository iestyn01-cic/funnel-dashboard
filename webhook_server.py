"""
Funnel Tracking Dashboard - Webhook Receiver & Server
=====================================================
Receives POST requests from Zapier, updates dashboard_data.json,
and serves the dashboard.

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
  python3 webhook_server.py
  (or background: tmux new-session -d -s dashboard 'python3 /workspace/webhook_server.py')
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

# Set an auth token to prevent random POSTs. Leave empty to disable.
# If set, Zapier must include "auth_token": "your_token" in every payload.
AUTH_TOKEN = ""

# ============================================================
# FLASK APP
# ============================================================
app = Flask(__name__, static_folder=WORKSPACE)


def load_data():
    """Load the current dashboard data from JSON file."""
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_data(data):
    """Save dashboard data to JSON file."""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


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
    return send_from_directory(WORKSPACE, "dashboard_data.json")


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
            "last_updated": dashboard_data["last_updated"]
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
        elif timeframe in ("daily", "weekly", "monthly"):
            reset_timeframe(dashboard_data, timeframe)
        else:
            return jsonify({"status": "error", "message": "Invalid timeframe"}), 400

        save_data(dashboard_data)
        return jsonify({"status": "success", "message": f"Reset {timeframe} data"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/webhook/status", methods=["GET"])
def status():
    """Health check endpoint."""
    data = load_data()
    return jsonify({
        "status": "online",
        "last_updated": data.get("last_updated", "never"),
        "data_file": DATA_FILE
    }), 200


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
            "calls_booked": 0, "booking_rate": 0
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
    print(f"")
    print(f"  Funnel Tracking Dashboard Server")
    print(f"  =================================")
    print(f"  Dashboard URL:  http://localhost:{PORT}/")
    print(f"  Webhook URL:    http://localhost:{PORT}/webhook")
    print(f"  Status URL:     http://localhost:{PORT}/webhook/status")
    print(f"  Data file:      {DATA_FILE}")
    print(f"  Auth token:     {'enabled' if AUTH_TOKEN else 'disabled'}")
    print(f"")
    print(f"  Press Ctrl+C to stop")
    print(f"")

    app.run(host="0.0.0.0", port=PORT, debug=False)