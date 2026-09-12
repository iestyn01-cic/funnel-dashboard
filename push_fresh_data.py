#!/usr/bin/env python3
"""Push fresh Meta Ads + Wistia data to the live dashboard webhook.
Data pulled September 12, 2026.
Date ranges: yesterday (Sept 11), last 7d (Sept 5-11), last 30d (Aug 13-Sept 11)
"""
import json
import urllib.request

DASHBOARD_URL = "https://funnel-dashboard-r0f0.onrender.com/webhook"

# ============================================================
# META ADS DATA - Pulled Sept 12, 2026 from live Meta API
# Account: act_1170401700483213
# ============================================================

# YESTERDAY (Sept 11, 2026)
daily_ads = {
    "spend": 492.51,
    "impressions": 5902,
    "clicks": 164,
    "link_clicks": 107,
    "reach": 4250,
    "frequency": 1.39,
    "cpm": 83.45,
    "ctr": 2.78,
    "link_ctr": 2.78,
    "cpc": 3.00,
    "leads": 2,
    "cost_per_lead": 246.26,
    "landing_page_views": 90,
}

# LAST 7 DAYS (Sept 5-11, 2026)
weekly_ads = {
    "spend": 2226.68,
    "impressions": 33278,
    "clicks": 999,
    "link_clicks": 665,
    "reach": 16504,
    "frequency": 2.02,
    "cpm": 66.91,
    "ctr": 3.00,
    "link_ctr": 3.00,
    "cpc": 2.23,
    "leads": 10,
    "cost_per_lead": 222.67,
    "landing_page_views": 505,
}

# LAST 30 DAYS (Aug 13 - Sept 11, 2026)
monthly_ads = {
    "spend": 13067.29,
    "impressions": 474085,
    "clicks": 16391,
    "link_clicks": 15447,
    "reach": 230572,
    "frequency": 2.06,
    "cpm": 27.56,
    "ctr": 3.46,
    "link_ctr": 3.46,
    "cpc": 0.80,
    "leads": 91,
    "cost_per_lead": 143.60,
    "landing_page_views": 3498,
}

# ============================================================
# WISTIA DATA - Pulled Sept 12, 2026
# Media: fsx8yduvoy
# API Key: cb7a932cd9ce57bdd5a72053df7f5c2e571ffabf7a43fae675c3b8e018a15952
# ============================================================
wistia_stats = {
    "page_loads": 1320,
    "visitors": 1108,
    "plays": 133,
    "play_rate": round(0.1092057761732852 * 100, 2),
    "avg_percent_watched": round(0.3498249936816309 * 100, 2),
    "hours_watched": 10.61,
    "vsl_name": "CiC VSL 2.0",
    "vsl_version": "2.0",
    "vsl_duration": 820.76,
}

# ============================================================
# PUSH TO DASHBOARD
# ============================================================
def push(timeframe, category, data):
    payload = json.dumps({
        "timeframe": timeframe,
        "category": category,
        "data": data,
    }).encode("utf-8")
    req = urllib.request.Request(
        DASHBOARD_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"  [{timeframe}.{category}] {result.get('status', 'unknown')}: {result.get('message', '')}")
            return True
    except Exception as e:
        print(f"  [{timeframe}.{category}] ERROR: {e}")
        return False

print("=" * 60)
print("PUSHING FRESH DATA TO DASHBOARD")
print(f"Date: Sept 12, 2026")
print(f"URL: {DASHBOARD_URL}")
print("=" * 60)

print("\n--- META ADS ---")
push("daily", "ads", daily_ads)
push("weekly", "ads", weekly_ads)
push("monthly", "ads", monthly_ads)

print("\n--- WISTIA (FUNNEL) ---")
push("daily", "funnel", wistia_stats)
push("weekly", "funnel", wistia_stats)
push("monthly", "funnel", wistia_stats)

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print(f"\n  DAILY (Sept 11):")
print(f"    Spend: ${daily_ads['spend']} | Impr: {daily_ads['impressions']} | CPM: ${daily_ads['cpm']}")
print(f"    Clicks: {daily_ads['clicks']} | Link Clicks: {daily_ads['link_clicks']} | CTR: {daily_ads['ctr']}% | CPC: ${daily_ads['cpc']}")
print(f"    Leads: {daily_ads['leads']} | CPL: ${daily_ads['cost_per_lead']}")
print(f"\n  WEEKLY (Sept 5-11):")
print(f"    Spend: ${weekly_ads['spend']} | Impr: {weekly_ads['impressions']} | CPM: ${weekly_ads['cpm']}")
print(f"    Clicks: {weekly_ads['clicks']} | Link Clicks: {weekly_ads['link_clicks']} | CTR: {weekly_ads['ctr']}% | CPC: ${weekly_ads['cpc']}")
print(f"    Leads: {weekly_ads['leads']} | CPL: ${weekly_ads['cost_per_lead']}")
print(f"\n  MONTHLY (Aug 13-Sept 11):")
print(f"    Spend: ${monthly_ads['spend']} | Impr: {monthly_ads['impressions']} | CPM: ${monthly_ads['cpm']}")
print(f"    Clicks: {monthly_ads['clicks']} | Link Clicks: {monthly_ads['link_clicks']} | CTR: {monthly_ads['ctr']}% | CPC: ${monthly_ads['cpc']}")
print(f"    Leads: {monthly_ads['leads']} | CPL: ${monthly_ads['cost_per_lead']}")
print(f"\n  WISTIA (all-time cumulative):")
print(f"    Loads: {wistia_stats['page_loads']} | Visitors: {wistia_stats['visitors']} | Plays: {wistia_stats['plays']}")
print(f"    Play Rate: {wistia_stats['play_rate']}% | Avg Watch: {wistia_stats['avg_percent_watched']}% | Hours: {wistia_stats['hours_watched']}")