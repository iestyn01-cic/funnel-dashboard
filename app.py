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

if __name__ == "__main__":
    print("\n  Funnel Tracking Dashboard Server")
    print("  ============================================================")
    print(f"  Dashboard URL:  http://localhost:{PORT}/")
    print(f"  Login URL:      http://localhost:{PORT}/login")
    print(f"  EOD URL:        http://localhost:{PORT}/eod")
    print(f"  Call Analysis:  http://localhost:{PORT}/call-analysis")
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