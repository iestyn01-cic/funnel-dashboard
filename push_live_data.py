#!/usr/bin/env python3
"""Push live Meta Ads + Wistia data to the dashboard webhook.
Pulls fresh data and pushes for daily (yesterday), weekly (7d), monthly (30d).
Funnel page_views uses ads landing_page_views only (NOT Wistia load_count).
"""
import json
import urllib.request
from datetime import datetime, timezone

DASHBOARD_URL = "https://funnel-dashboard-r0f0.onrender.com/webhook"

# ============================================================
# META ADS DATA - Pulled Sept 12, 2026 from live Meta API
# Account: act_1170401700483213
# ============================================================

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
    "video_views": 1503,
    "date_range": "Sept 11, 2026",
}

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
    "video_views": 7819,
    "date_range": "Sept 5-11, 2026",
}

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
    "video_views": 109286,
    "date_range": "Aug 13 - Sept 11, 2026",
}

# ============================================================
# WISTIA DATA - Pulled Sept 12, 2026
# Media: fsx8yduvoy (CiC VSL 2.0)
# ============================================================
wistia_stats = {
    "page_loads": 1329,
    "visitors": 1114,
    "plays": 134,
    "play_rate": round(0.10951526032315978 * 100, 2),
    "avg_percent_watched": round(0.3484922612794985 * 100, 2),
    "hours_watched": round(10.646616700355555, 2),
    "vsl_name": "CiC VSL 2.0",
    "vsl_version": "2.0",
    "vsl_duration": 820.76,
}

# ============================================================
# FUNNEL LAYER - page_views from ADS landing_page_views only
# (Wistia load_count excluded per user instruction to avoid inflation)
# ============================================================
daily_funnel = {
    "page_views": 90,        # from ads landing_page_views
    "vsl_plays": 134,
    "vsl_play_rate": wistia_stats["play_rate"],
    "vsl_avg_watched": wistia_stats["avg_percent_watched"],
    "vsl_hours_watched": wistia_stats["hours_watched"],
    "vsl_visitors": wistia_stats["visitors"],
    "vsl_name": wistia_stats["vsl_name"],
}
weekly_funnel = {
    "page_views": 505,
    "vsl_plays": 134,
    "vsl_play_rate": wistia_stats["play_rate"],
    "vsl_avg_watched": wistia_stats["avg_percent_watched"],
    "vsl_hours_watched": wistia_stats["hours_watched"],
    "vsl_visitors": wistia_stats["visitors"],
    "vsl_name": wistia_stats["vsl_name"],
}
monthly_funnel = {
    "page_views": 3498,
    "vsl_plays": 134,
    "vsl_play_rate": wistia_stats["play_rate"],
    "vsl_avg_watched": wistia_stats["avg_percent_watched"],
    "vsl_hours_watched": wistia_stats["hours_watched"],
    "vsl_visitors": wistia_stats["visitors"],
    "vsl_name": wistia_stats["vsl_name"],
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
print("PUSHING LIVE DATA TO DASHBOARD")
print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
print(f"URL: {DASHBOARD_URL}")
print("=" * 60)

print("\n--- META ADS ---")
push("daily", "ads", daily_ads)
push("weekly", "ads", weekly_ads)
push("monthly", "ads", monthly_ads)

print("\n--- FUNNEL (Wistia VSL + ads landing page views) ---")
push("daily", "funnel", daily_funnel)
push("weekly", "funnel", weekly_funnel)
push("monthly", "funnel", monthly_funnel)

print("\n" + "=" * 60)
print("PUSH COMPLETE")
print("=" * 60)
print(f"\n  DAILY (Sept 11):")
print(f"    Spend: ${daily_ads['spend']} | Impr: {daily_ads['impressions']} | CPM: ${daily_ads['cpm']}")
print(f"    Link Clicks: {daily_ads['link_clicks']} | CTR: {daily_ads['ctr']}% | CPC: ${daily_ads['cpc']}")
print(f"    Leads: {daily_ads['leads']} | CPL: ${daily_ads['cost_per_lead']} | LPV: {daily_ads['landing_page_views']}")
print(f"\n  WEEKLY (Sept 5-11):")
print(f"    Spend: ${weekly_ads['spend']} | Impr: {weekly_ads['impressions']} | CPM: ${weekly_ads['cpm']}")
print(f"    Link Clicks: {weekly_ads['link_clicks']} | CTR: {weekly_ads['ctr']}% | CPC: ${weekly_ads['cpc']}")
print(f"    Leads: {weekly_ads['leads']} | CPL: ${weekly_ads['cost_per_lead']} | LPV: {weekly_ads['landing_page_views']}")
print(f"\n  MONTHLY (Aug 13-Sept 11):")
print(f"    Spend: ${monthly_ads['spend']} | Impr: {monthly_ads['impressions']} | CPM: ${monthly_ads['cpm']}")
print(f"    Link Clicks: {monthly_ads['link_clicks']} | CTR: {monthly_ads['ctr']}% | CPC: ${monthly_ads['cpc']}")
print(f"    Leads: {monthly_ads['leads']} | CPL: ${monthly_ads['cost_per_lead']} | LPV: {monthly_ads['landing_page_views']}")
print(f"\n  WISTIA VSL (cumulative):")
print(f"    Loads: {wistia_stats['page_loads']} | Visitors: {wistia_stats['visitors']} | Plays: {wistia_stats['plays']}")
print(f"    Play Rate: {wistia_stats['play_rate']}% | Avg Watch: {wistia_stats['avg_percent_watched']}% | Hours: {wistia_stats['hours_watched']}")