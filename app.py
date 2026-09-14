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
from flask import Flask, request, jsonify, send_file, redirect, session

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

# ============================================================
# DATA LOAD / SAVE
# ============================================================
def load_data():
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT data FROM dashboard_data ORDER BY updated_at DESC LIMIT 1;")
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row:
                return row[0] if isinstance(row[0], dict) else json.loads(row[0])
        except Exception:
            pass
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return get_default_data()

def save_data(data):
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO dashboard_data (data) VALUES (%s);", (json.dumps(data),))
            conn.commit()
            cur.close()
            conn.close()
            return
        except Exception:
            pass
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_default_data():
    return {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "daily": {"date": "", "ads": {}, "funnel": {}, "sales": {}, "source": {}, "keystone": {}},
        "weekly": {"week_of": "", "ads": {}, "funnel": {}, "sales": {}, "source": {}, "keystone": {}},
        "monthly": {"month": "", "ads": {}, "funnel": {}, "sales": {}, "source": {}, "keystone": {}, "closers": [], "setters": []},
        "eod_entries": [],
        "setter_eod_entries": [],
        "call_links": [],
        "benchmarks": {
            "link_ctr": 2.0, "page_conversion_rate": 3.0, "show_rate": 70.0,
            "close_rate": 25.0, "retention_to_pitch": 80.0, "booking_rate": 30.0,
            "roas": 2.0, "play_rate": 20.0, "avg_watched": 40.0,
        },
    }

# ============================================================
# AUTH HELPERS
# ============================================================
def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def check_auth(required_role=None):
    if "user_id" not in session:
        return False
    if required_role and session.get("role") != required_role and session.get("role") != "admin":
        return False
    return True

def get_current_user():
    if "user_id" not in session:
        return None
    return {"id": session.get("user_id"), "name": session.get("name"), "role": session.get("role"), "email": session.get("email")}

# ============================================================
# DERIVED METRICS
# ============================================================
def safe_div(a, b):
    return round(a / b, 2) if b else 0

def recalculate_derived(data):
    for tf in ("daily", "weekly", "monthly"):
        if tf not in data:
            continue
        ads = data[tf].get("ads", {})
        funnel = data[tf].get("funnel", {})
        sales = data[tf].get("sales", {})
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
        form_subs = funnel.get("form_submissions", 0) or 0
        calls_booked_f = funnel.get("calls_booked", 0) or 0
        if page_views > 0:
            funnel["page_conversion_rate"] = round((form_subs / page_views) * 100, 2)
        if form_subs > 0:
            funnel["booking_rate"] = round((calls_booked_f / form_subs) * 100, 2)
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
        data[tf]["keystone"] = {
            "roas": safe_div(revenue, spend),
            "cost_per_booked_call": safe_div(spend, calls_booked),
            "cost_per_showed_call": safe_div(spend, calls_showed),
            "cost_per_closed_deal": safe_div(spend, calls_closed),
            "collected_per_booked_call": safe_div(revenue, calls_booked),
            "collected_per_showed_call": safe_div(revenue, calls_showed),
        }

# ============================================================
# EOD AGGREGATION
# ============================================================
def aggregate_eod_to_sales(data):
    conn = get_db()
    entries = []
    setter_entries = []
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM eod_entries ORDER BY date DESC;")
            cols = [d[0] for d in cur.description]
            for row in cur.fetchall():
                entries.append(dict(zip(cols, row)))
            cur.execute("SELECT * FROM setter_eod_entries ORDER BY date DESC;")
            cols2 = [d[0] for d in cur.description]
            for row in cur.fetchall():
                setter_entries.append(dict(zip(cols2, row)))
            cur.close()
            conn.close()
        except Exception:
            pass
    else:
        entries = data.get("eod_entries", [])
        setter_entries = data.get("setter_eod_entries", [])

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    for tf, cutoff in [("daily", today), ("weekly", week_ago), ("monthly", month_ago)]:
        tf_entries = [e for e in entries if e.get("date", "") >= cutoff]
        if not tf_entries:
            continue
        sales = data[tf].setdefault("sales", {})
        sales["calls_booked"] = sum(e.get("calls_booked", 0) or 0 for e in tf_entries)
        sales["calls_showed"] = sum(e.get("calls_showed", 0) or 0 for e in tf_entries)
        sales["calls_closed"] = sum(e.get("calls_closed", 0) or 0 for e in tf_entries)
        sales["revenue_collected"] = sum(float(e.get("revenue_collected", 0) or 0) for e in tf_entries)
        sales["cash_full_pay"] = sum(float(e.get("cash_full_pay", 0) or 0) for e in tf_entries)
        sales["cash_payment_plans"] = sum(float(e.get("cash_payment_plans", 0) or 0) for e in tf_entries)
        source = data[tf].setdefault("source", {})
        source["ad_revenue"] = sum(float(e.get("ad_sourced_revenue", 0) or 0) for e in tf_entries)
        source["organic_revenue"] = sum(float(e.get("organic_sourced_revenue", 0) or 0) for e in tf_entries)
        source["ad_calls_booked"] = sum(e.get("ad_calls_booked", 0) or 0 for e in tf_entries)
        source["ad_calls_showed"] = sum(e.get("ad_calls_showed", 0) or 0 for e in tf_entries)
        source["ad_calls_closed"] = sum(e.get("ad_calls_closed", 0) or 0 for e in tf_entries)
        source["organic_calls_booked"] = sum(e.get("organic_calls_booked", 0) or 0 for e in tf_entries)
        source["organic_calls_showed"] = sum(e.get("organic_calls_showed", 0) or 0 for e in tf_entries)
        source["organic_calls_closed"] = sum(e.get("organic_calls_closed", 0) or 0 for e in tf_entries)

        if tf == "monthly":
            closer_map = {}
            for e in tf_entries:
                name = e.get("closer_name", "Unknown")
                if name not in closer_map:
                    closer_map[name] = {"name": name, "calls_booked": 0, "calls_showed": 0, "calls_closed": 0, "revenue_collected": 0}
                closer_map[name]["calls_booked"] += e.get("calls_booked", 0) or 0
                closer_map[name]["calls_showed"] += e.get("calls_showed", 0) or 0
                closer_map[name]["calls_closed"] += e.get("calls_closed", 0) or 0
                closer_map[name]["revenue_collected"] += float(e.get("revenue_collected", 0) or 0)
            data[tf]["closers"] = list(closer_map.values())

            setter_map = {}
            for e in setter_entries:
                if e.get("date", "") >= cutoff:
                    name = e.get("setter_name", "Unknown")
                    if name not in setter_map:
                        setter_map[name] = {"name": name, "outreach_sent": 0, "calls_booked": 0, "calls_showed": 0, "calls_closed": 0}
                    setter_map[name]["outreach_sent"] += e.get("outreach_sent", 0) or 0
                    setter_map[name]["calls_booked"] += e.get("calls_booked", 0) or 0
                    setter_map[name]["calls_showed"] += e.get("calls_showed", 0) or 0
                    setter_map[name]["calls_closed"] += e.get("calls_closed", 0) or 0
            data[tf]["setters"] = list(setter_map.values())

# ============================================================
# WISTIA PULL
# ============================================================
def pull_wistia():
    if not WISTIA_API_KEY:
        return None
    try:
        url = f"https://api.wistia.com/v1/stats/medias/{WISTIA_MEDIA_ID}.json"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {WISTIA_API_KEY}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            stats = json.loads(resp.read().decode("utf-8"))
        return {
            "page_loads": stats.get("load_count", 0),
            "visitors": stats.get("visitors", 0),
            "plays": stats.get("play_count", 0),
            "play_rate": round(stats.get("play_rate", 0) * 100, 2),
            "avg_percent_watched": round(stats.get("engagement", 0) * 100, 2),
            "hours_watched": round(stats.get("hours_watched", 0), 2),
            "vsl_name": "CiC VSL 2.0",
            "vsl_version": "2.0",
            "vsl_duration": 820.76,
        }
    except Exception as e:
        print(f"Wistia pull error: {e}")
        return None

# ============================================================
# ROUTES - PAGES
# ============================================================
@app.route("/")
def index():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return send_file(os.path.join(BASE_DIR, "dashboard.html"))

@app.route("/login")
def login_page():
    return send_file(os.path.join(BASE_DIR, "login.html"))

@app.route("/eod")
def eod_page():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return send_file(os.path.join(BASE_DIR, "eod.html"))

@app.route("/call-analysis")
def call_analysis_page():
    user = get_current_user()
    if not user:
        return redirect("/login")
    return send_file(os.path.join(BASE_DIR, "call_analysis.html"))

# ============================================================
# API - AUTH
# ============================================================
@app.route("/api/auth/login", methods=["POST"])
def api_login():
    body = request.get_json(force=True, silent=True) or {}
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    try:
        conn = get_db()
        if not conn:
            status = db_status()
            return jsonify({"error": f"Database connection failed: {status.get('error', 'unknown')}"}), 500
        cur = conn.cursor()
        cur.execute("SELECT id, email, password_hash, name, role FROM users WHERE email = %s;", (email,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row or row[2] != hash_password(password):
            return jsonify({"error": "Invalid credentials"}), 401
        session.permanent = True
        session["user_id"] = row[0]
        session["email"] = row[1]
        session["name"] = row[3]
        session["role"] = row[4]
        return jsonify({"status": "ok", "user": {"name": row[3], "role": row[4], "email": row[1]}})
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"status": "ok"})

@app.route("/api/auth/me")
def api_me():
    user = get_current_user()
    if not user:
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True, "user": user})

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    if not check_auth("admin"):
        return jsonify({"error": "Admin only"}), 403
    body = request.get_json(force=True, silent=True) or {}
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    name = body.get("name", "")
    role = body.get("role", "closer")
    if role not in ("admin", "closer", "setter"):
        role = "closer"
    if not email or not password or not name:
        return jsonify({"error": "Missing fields"}), 400
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (%s, %s, %s, %s);",
            (email, hash_password(password), name, role)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"error": "User already exists"}), 409
    cur.close()
    conn.close()
    return jsonify({"status": "ok", "message": f"Created {role} account for {name}"})

@app.route("/api/db-status")
def api_db_status():
    return jsonify(db_status())

# ============================================================
# API - DASHBOARD DATA
# ============================================================
@app.route("/dashboard_data.json")
def get_dashboard_data():
    data = load_data()
    recalculate_derived(data)
    aggregate_eod_to_sales(data)
    recalculate_derived(data)
    user = get_current_user()
    if user and user["role"] in ("closer", "setter"):
        data["restricted"] = True
        data["user_role"] = user["role"]
        data["user_name"] = user["name"]
    return jsonify(data)

# ============================================================
# WEBHOOK - DATA PUSH
# ============================================================
@app.route("/webhook", methods=["POST"])
def webhook():
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if AUTH_TOKEN and token != AUTH_TOKEN:
        pass
    body = request.get_json(force=True, silent=True) or {}
    timeframe = body.get("timeframe")
    category = body.get("category")
    new_data = body.get("data", {})
    if not timeframe or not category:
        return jsonify({"status": "error", "message": "Missing timeframe or category"}), 400
    data = load_data()
    if timeframe not in data:
        data[timeframe] = {}
    if category == "ads":
        existing = data[timeframe].get("ads", {})
        existing.update(new_data)
        data[timeframe]["ads"] = existing
    elif category == "funnel":
        existing = data[timeframe].get("funnel", {})
        existing.update(new_data)
        data[timeframe]["funnel"] = existing
    elif category == "sales":
        existing = data[timeframe].get("sales", {})
        existing.update(new_data)
        data[timeframe]["sales"] = existing
    elif category == "source":
        existing = data[timeframe].get("source", {})
        existing.update(new_data)
        data[timeframe]["source"] = existing
    recalculate_derived(data)
    save_data(data)
    return jsonify({"status": "success", "message": f"Updated {timeframe}.{category}"})

@app.route("/webhook/status")
def webhook_status():
    data = load_data()
    return jsonify({"status": "ok", "last_updated": data.get("last_updated", "unknown")})

# ============================================================
# API - EOD (CLOSER)
# ============================================================
@app.route("/api/eod", methods=["GET"])
def api_get_eod():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    user = get_current_user()
    conn = get_db()
    if not conn:
        data = load_data()
        return jsonify(data.get("eod_entries", []))
    cur = conn.cursor()
    if user["role"] == "admin":
        cur.execute("SELECT * FROM eod_entries ORDER BY date DESC, created_at DESC;")
    else:
        cur.execute("SELECT * FROM eod_entries WHERE closer_name = %s ORDER BY date DESC, created_at DESC;", (user["name"],))
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        if isinstance(r.get("updated_at"), datetime):
            r["updated_at"] = r["updated_at"].isoformat()
        for k in ("revenue_collected", "cash_full_pay", "cash_payment_plans", "ad_sourced_revenue", "organic_sourced_revenue"):
            if r.get(k) is not None:
                r[k] = float(r[k])
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/eod/submit", methods=["POST"])
def api_submit_eod():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    body = request.get_json(force=True, silent=True) or {}
    user = get_current_user()
    closer_name = body.get("closer_name", user["name"] if user else "Unknown")
    date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    conn = get_db()
    if not conn:
        data = load_data()
        entry = {**body, "closer_name": closer_name, "date": date, "id": len(data.get("eod_entries", [])) + 1}
        data.setdefault("eod_entries", []).append(entry)
        save_data(data)
        return jsonify({"status": "ok", "entry": entry})
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO eod_entries (date, closer_name, calls_booked, calls_showed, calls_closed, calls_no_show,
            revenue_collected, cash_full_pay, cash_payment_plans, ad_sourced_revenue, organic_sourced_revenue,
            ad_calls_booked, ad_calls_showed, ad_calls_closed, organic_calls_booked, organic_calls_showed, organic_calls_closed,
            notes, call_link)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
    """, (
        date, closer_name,
        int(body.get("calls_booked", 0) or 0), int(body.get("calls_showed", 0) or 0),
        int(body.get("calls_closed", 0) or 0), int(body.get("calls_no_show", 0) or 0),
        float(body.get("revenue_collected", 0) or 0), float(body.get("cash_full_pay", 0) or 0),
        float(body.get("cash_payment_plans", 0) or 0), float(body.get("ad_sourced_revenue", 0) or 0),
        float(body.get("organic_sourced_revenue", 0) or 0),
        int(body.get("ad_calls_booked", 0) or 0), int(body.get("ad_calls_showed", 0) or 0),
        int(body.get("ad_calls_closed", 0) or 0), int(body.get("organic_calls_booked", 0) or 0),
        int(body.get("organic_calls_showed", 0) or 0), int(body.get("organic_calls_closed", 0) or 0),
        body.get("notes", ""), body.get("call_link", "")
    ))
    entry_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok", "id": entry_id})

@app.route("/api/eod/update", methods=["PUT"])
def api_update_eod():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    body = request.get_json(force=True, silent=True) or {}
    entry_id = body.get("id")
    if not entry_id:
        return jsonify({"error": "Missing id"}), 400
    user = get_current_user()
    conn = get_db()
    if not conn:
        return jsonify({"error": "Database required for updates"}), 500
    cur = conn.cursor()
    if user["role"] != "admin":
        cur.execute("SELECT closer_name FROM eod_entries WHERE id = %s;", (entry_id,))
        row = cur.fetchone()
        if not row or row[0] != user["name"]:
            cur.close()
            conn.close()
            return jsonify({"error": "Can only edit your own entries"}), 403
    fields = ["calls_booked", "calls_showed", "calls_closed", "calls_no_show",
              "revenue_collected", "cash_full_pay", "cash_payment_plans",
              "ad_sourced_revenue", "organic_sourced_revenue",
              "ad_calls_booked", "ad_calls_showed", "ad_calls_closed",
              "organic_calls_booked", "organic_calls_showed", "organic_calls_closed",
              "notes", "call_link"]
    sets = []
    vals = []
    for f in fields:
        if f in body:
            sets.append(f"{f} = %s")
            vals.append(body[f])
    sets.append("updated_at = NOW()")
    vals.append(entry_id)
    cur.execute(f"UPDATE eod_entries SET {', '.join(sets)} WHERE id = %s;", vals)
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok", "message": "EOD entry updated"})

@app.route("/api/eod/<int:entry_id>", methods=["DELETE"])
def api_delete_eod(entry_id):
    if not check_auth("admin"):
        return jsonify({"error": "Admin only"}), 403
    conn = get_db()
    if not conn:
        return jsonify({"error": "Database required"}), 500
    cur = conn.cursor()
    cur.execute("DELETE FROM eod_entries WHERE id = %s;", (entry_id,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================================
# API - SETTER EOD
# ============================================================
@app.route("/api/eod/setter", methods=["GET"])
def api_get_setter_eod():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    user = get_current_user()
    conn = get_db()
    if not conn:
        data = load_data()
        return jsonify(data.get("setter_eod_entries", []))
    cur = conn.cursor()
    if user["role"] == "admin":
        cur.execute("SELECT * FROM setter_eod_entries ORDER BY date DESC, created_at DESC;")
    else:
        cur.execute("SELECT * FROM setter_eod_entries WHERE setter_name = %s ORDER BY date DESC, created_at DESC;", (user["name"],))
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
        if isinstance(r.get("updated_at"), datetime):
            r["updated_at"] = r["updated_at"].isoformat()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/eod/setter/submit", methods=["POST"])
def api_submit_setter_eod():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    body = request.get_json(force=True, silent=True) or {}
    user = get_current_user()
    setter_name = body.get("setter_name", user["name"] if user else "Unknown")
    date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    conn = get_db()
    if not conn:
        data = load_data()
        entry = {**body, "setter_name": setter_name, "date": date}
        data.setdefault("setter_eod_entries", []).append(entry)
        save_data(data)
        return jsonify({"status": "ok", "entry": entry})
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO setter_eod_entries (date, setter_name, outreach_sent, replies_received, calls_booked, calls_showed, calls_closed, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
    """, (
        date, setter_name,
        int(body.get("outreach_sent", 0) or 0), int(body.get("replies_received", 0) or 0),
        int(body.get("calls_booked", 0) or 0), int(body.get("calls_showed", 0) or 0),
        int(body.get("calls_closed", 0) or 0), body.get("notes", "")
    ))
    entry_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok", "id": entry_id})

@app.route("/api/eod/setter/update", methods=["PUT"])
def api_update_setter_eod():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    body = request.get_json(force=True, silent=True) or {}
    entry_id = body.get("id")
    if not entry_id:
        return jsonify({"error": "Missing id"}), 400
    user = get_current_user()
    conn = get_db()
    if not conn:
        return jsonify({"error": "Database required"}), 500
    cur = conn.cursor()
    if user["role"] != "admin":
        cur.execute("SELECT setter_name FROM setter_eod_entries WHERE id = %s;", (entry_id,))
        row = cur.fetchone()
        if not row or row[0] != user["name"]:
            cur.close()
            conn.close()
            return jsonify({"error": "Can only edit your own entries"}), 403
    fields = ["outreach_sent", "replies_received", "calls_booked", "calls_showed", "calls_closed", "notes"]
    sets = []
    vals = []
    for f in fields:
        if f in body:
            sets.append(f"{f} = %s")
            vals.append(body[f])
    sets.append("updated_at = NOW()")
    vals.append(entry_id)
    cur.execute(f"UPDATE setter_eod_entries SET {', '.join(sets)} WHERE id = %s;", vals)
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"})

# ============================================================
# API - CALL LINKS
# ============================================================
@app.route("/api/call-links", methods=["GET"])
def api_get_call_links():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    conn = get_db()
    if not conn:
        data = load_data()
        return jsonify(data.get("call_links", []))
    cur = conn.cursor()
    user = get_current_user()
    if user["role"] == "admin":
        cur.execute("SELECT * FROM call_links ORDER BY date DESC, created_at DESC;")
    else:
        cur.execute("SELECT * FROM call_links WHERE closer_name = %s ORDER BY date DESC, created_at DESC;", (user["name"],))
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    for r in rows:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    cur.close()
    conn.close()
    return jsonify(rows)

@app.route("/api/call-links/submit", methods=["POST"])
def api_submit_call_link():
    if not check_auth():
        return jsonify({"error": "Not authenticated"}), 401
    body = request.get_json(force=True, silent=True) or {}
    user = get_current_user()
    closer_name = body.get("closer_name", user["name"] if user else "Unknown")
    date = body.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    conn = get_db()
    if not conn:
        data = load_data()
        entry = {**body, "closer_name": closer_name, "date": date}
        data.setdefault("call_links", []).append(entry)
        save_data(data)
        return jsonify({"status": "ok"})
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO call_links (date, closer_name, call_link, prospect_name, outcome, transcript, analysis)
        VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;
    """, (date, closer_name, body.get("call_link", ""), body.get("prospect_name", ""),
          body.get("outcome", ""), body.get("transcript", ""), body.get("analysis", "")))
    entry_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok", "id": entry_id})

# ============================================================
# CRON - AUTOMATED DATA PULLS
# ============================================================
@app.route("/cron/update-wistia", methods=["POST", "GET"])
def cron_update_wistia():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if secret != CRON_SECRET and not request.args.get("force"):
        return jsonify({"error": "Unauthorized"}), 401
    wistia = pull_wistia()
    if not wistia:
        return jsonify({"status": "error", "message": "Wistia pull failed"}), 500
    data = load_data()
    for tf in ("daily", "weekly", "monthly"):
        existing = data[tf].get("funnel", {})
        existing.update(wistia)
        data[tf]["funnel"] = existing
    recalculate_derived(data)
    save_data(data)
    return jsonify({"status": "ok", "wistia": wistia})

@app.route("/cron/update-all", methods=["POST", "GET"])
def cron_update_all():
    secret = request.headers.get("X-Cron-Secret", "") or request.args.get("secret", "")
    if secret != CRON_SECRET and not request.args.get("force"):
        return jsonify({"error": "Unauthorized"}), 401
    results = {}
    wistia = pull_wistia()
    if wistia:
        results["wistia"] = "ok"
        data = load_data()
        for tf in ("daily", "weekly", "monthly"):
            existing = data[tf].get("funnel", {})
            existing.update(wistia)
            data[tf]["funnel"] = existing
        recalculate_derived(data)
        save_data(data)
    else:
        results["wistia"] = "failed"
    results["meta"] = "handled_by_agent_trigger"
    return jsonify({"status": "ok", "results": results})

# ============================================================
# MAIN
# ============================================================

try:
    if DATABASE_URL:
        print("  Database: PostgreSQL (persistent)")
        init_db()
    else:
        print("  Database: File-based (NOT persistent - set DATABASE_URL)")
except Exception as e:
    print(f"  Database init error (non-fatal): {e}")

if __name__ == "__main__":
    print(f"\n  Funnel Tracking Dashboard Server")
    print(f"  =================================")
    print(f"  Dashboard URL:  http://localhost:{PORT}/")
    print(f"  Login URL:      http://localhost:{PORT}/login")
    print(f"  EOD URL:        http://localhost:{PORT}/eod")
    print(f"  Call Analysis:  http://localhost:{PORT}/call-analysis")
    print(f"  Cron Wistia:    http://localhost:{PORT}/cron/update-wistia")
    print(f"  Cron All:       http://localhost:{PORT}/cron/update-all")
    print(f"\n  Press Ctrl+C to stop\n")
    app.run(host="0.0.0.0", port=PORT, debug=False)