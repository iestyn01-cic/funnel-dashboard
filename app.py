#!/usr/bin/env python3
"""
Funnel Tracking Dashboard - Full Build
Role-based auth, EOD CRUD, setter EOD, call analysis, hourly automation.
"""
import os
import json
import hashlib
import secrets
import urllib.request
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, send_file, send_from_directory, redirect, session

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", secrets.token_hex(32))
app.permanent_session_lifetime = timedelta(days=7)

PORT = int(os.environ.get("PORT", 8080))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
AUTH_TOKEN = os.environ.get("AUTH_TOKEN", "")
WISTIA_API_KEY = os.environ.get("WISTIA_API_KEY", "")
WISTIA_MEDIA_ID = os.environ.get("WISTIA_MEDIA_ID", "fsx8yduvoy")
CRON_SECRET = os.environ.get("CRON_SECRET", "funnel-dash-cron-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "dashboard_data.json")

# ============================================================
# DATABASE
# ============================================================
def get_db():
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, connect_timeout=10)
    except Exception as e:
        print(f"DB connection error: {e}")
        return None

def db_status():
    """Return diagnostic info about the database connection."""
    if not DATABASE_URL:
        return {"configured": False, "connected": False, "error": "DATABASE_URL not set"}
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users;")
        user_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return {"configured": True, "connected": True, "users": user_count, "error": None}
    except Exception as e:
        return {"configured": True, "connected": False, "error": str(e)}

def init_db():
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'closer',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eod_entries (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            closer_name TEXT NOT NULL,
            calls_booked INT DEFAULT 0,
            calls_showed INT DEFAULT 0,
            calls_closed INT DEFAULT 0,
            calls_no_show INT DEFAULT 0,
            revenue_collected DECIMAL(12,2) DEFAULT 0,
            cash_full_pay DECIMAL(12,2) DEFAULT 0,
            cash_payment_plans DECIMAL(12,2) DEFAULT 0,
            ad_sourced_revenue DECIMAL(12,2) DEFAULT 0,
            organic_sourced_revenue DECIMAL(12,2) DEFAULT 0,
            notes TEXT DEFAULT '',
            call_link TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    # Add ad/organic call breakdown columns if they don't exist
    try:
        cur.execute("ALTER TABLE eod_entries ADD COLUMN IF NOT EXISTS ad_calls_booked INT DEFAULT 0;")
        cur.execute("ALTER TABLE eod_entries ADD COLUMN IF NOT EXISTS ad_calls_showed INT DEFAULT 0;")
        cur.execute("ALTER TABLE eod_entries ADD COLUMN IF NOT EXISTS ad_calls_closed INT DEFAULT 0;")
        cur.execute("ALTER TABLE eod_entries ADD COLUMN IF NOT EXISTS organic_calls_booked INT DEFAULT 0;")
        cur.execute("ALTER TABLE eod_entries ADD COLUMN IF NOT EXISTS organic_calls_showed INT DEFAULT 0;")
        cur.execute("ALTER TABLE eod_entries ADD COLUMN IF NOT EXISTS organic_calls_closed INT DEFAULT 0;")
    except Exception:
        pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS setter_eod_entries (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            setter_name TEXT NOT NULL,
            outreach_sent INT DEFAULT 0,
            replies_received INT DEFAULT 0,
            calls_booked INT DEFAULT 0,
            calls_showed INT DEFAULT 0,
            calls_closed INT DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS call_links (
            id SERIAL PRIMARY KEY,
            date TEXT NOT NULL,
            closer_name TEXT NOT NULL,
            call_link TEXT NOT NULL,
            prospect_name TEXT DEFAULT '',
            outcome TEXT DEFAULT '',
            transcript TEXT DEFAULT '',
            analysis TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    # Seed default admin if no users exist
    cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin';")
    if cur.fetchone()[0] == 0:
        admin_pass = hashlib.sha256("admin123".encode()).hexdigest()
        cur.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (%s, %s, %s, %s)",
            ("admin@congruenceinclosing.com", admin_pass, "Admin", "admin")
        )
    conn.commit()
    cur.close()
    conn.close()

@app.route("/api/db-status")
def api_db_status():
    return jsonify(db_status())

@app.route("/api/init-db", methods=["POST", "GET"])
def api_init_db():
    try:
        init_db()
        status = db_status()
        return jsonify({"status": "ok", "message": "Database initialized", "db_status": status})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ============================================================
# DASHBOARD DATA (JSON file-based, for webhook + dashboard.html)
# ============================================================
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

def safe_div(numerator, denominator):
    """Safe division returning 0 on divide-by-zero."""
    try:
        if denominator and denominator != 0:
            return round(numerator / denominator, 2)
    except (TypeError, ZeroDivisionError):
        pass
    return 0

# ============================================================
# DASHBOARD ROUTES
# ============================================================
@app.route("/")
def dashboard():
    return send_from_directory(BASE_DIR, "dashboard.html")

@app.route("/dashboard_data.json")
def data_endpoint():
    return send_from_directory(BASE_DIR, "dashboard_data.json")

# ============================================================
# WEBHOOK RECEIVER
# ============================================================
@app.route("/webhook", methods=["POST"])
def receive_webhook():
    """Receive data from automation and update the dashboard."""
    try:
        payload = request.get_json(force=True, silent=True)
        if not payload:
            return jsonify({"status": "error", "message": "No JSON body received"}), 400

        timeframe = payload.get("timeframe", "daily").lower()
        category = payload.get("category", "").lower()
        data = payload.get("data", {})

        if timeframe not in ("daily", "weekly", "monthly"):
            return jsonify({"status": "error", "message": f"Invalid timeframe: {timeframe}"}), 400

        if category not in ("ads", "funnel", "sales", "closers", "setters"):
            return jsonify({"status": "error", "message": f"Invalid category: {category}"}), 400

        if not data:
            return jsonify({"status": "error", "message": "No data provided"}), 400

        dashboard_data = load_data()

        if category in ("closers", "setters"):
            person_name = data.get("name", "").strip()
            if not person_name:
                return jsonify({"status": "error", "message": "Closers/setters require a 'name' field"}), 400

            people_list = dashboard_data.get(timeframe, {}).get(category, [])
            if not isinstance(people_list, list):
                people_list = []

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
            if timeframe not in dashboard_data:
                dashboard_data[timeframe] = {}
            if category not in dashboard_data[timeframe]:
                dashboard_data[timeframe][category] = {}
            deep_merge(dashboard_data[timeframe][category], data)

        recalculate_keystones(dashboard_data)
        recalculate_derived_metrics(dashboard_data)
        save_data(dashboard_data)

        return jsonify({
            "status": "success",
            "message": f"Updated {timeframe}.{category}",
            "last_updated": dashboard_data["last_updated"]
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/webhook/status", methods=["GET"])
def webhook_status():
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
def recalculate_keystones(dashboard_data):
    """Recalculate keystone metrics for weekly and monthly."""
    for tf in ("weekly", "monthly"):
        if tf not in dashboard_data:
            continue
        ads = dashboard_data[tf].get("ads", {})
        sales = dashboard_data[tf].get("sales", {})
        spend = ads.get("spend", 0) or 0
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
    """Auto-calculate derived metrics from raw inputs."""
    for tf in ("daily", "weekly", "monthly"):
        if tf not in dashboard_data:
            continue
        ads = dashboard_data[tf].get("ads", {})
        funnel = dashboard_data[tf].get("funnel", {})
        sales = dashboard_data[tf].get("sales", {})
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
        page_views = funnel.get("page_views", 0) or 0
        form_submissions = funnel.get("form_submissions", 0) or 0
        calls_booked_funnel = funnel.get("calls_booked", 0) or 0
        if page_views > 0:
            funnel["page_conversion_rate"] = round((form_submissions / page_views) * 100, 2)
        if form_submissions > 0:
            funnel["booking_rate"] = round((calls_booked_funnel / form_submissions) * 100, 2)
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

if __name__ == "__main__":
    print("\n  Funnel Tracking Dashboard Server")
    print("  ============================================================")
    print(f"  Dashboard URL:  http://localhost:{PORT}/")
    print(f"  Login URL:      http://localhost:{PORT}/login")
    print(f"  EOD URL:        http://localhost:{PORT}/eod")
    print(f"  Call Analysis:  http://localhost:{PORT}/call-analysis")
    print(f"  Webhook URL:    http://localhost:{PORT}/webhook")
    print(f"  Cron Wistia:    http://localhost:{PORT}/cron/update-wistia")
    print(f"  Cron All:       http://localhost:{PORT}/cron/update-all")
    print(f"\n  Press Ctrl+C to stop\n")
    try:
        if DATABASE_URL:
            print("  Database: PostgreSQL (persistent)")
            init_db()
        else:
            print("  Database: File-based (NOT persistent - set DATABASE_URL)")
    except Exception as e:
        print(f"  Database init error (non-fatal): {e}")
    app.run(host="0.0.0.0", port=PORT, debug=False)
