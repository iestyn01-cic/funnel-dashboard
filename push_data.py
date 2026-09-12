#!/usr/bin/env python3
"""Push Meta Ads + Wistia data to the live dashboard webhook."""
import json
import urllib.request

DASHBOARD_URL = "https://funnel-dashboard-r0f0.onrender.com/webhook"

# ============================================================
# META ADS DATA (pulled from Graph API)
# ============================================================

# Yesterday (Sept 6) - Thunderdome campaign only (only active campaign)
# spend: 35.38, impressions: 742, link_clicks: 17, leads: 15
daily_ads = {
    "spend": 35.38,
    "impressions": 742,
    "clicks": 17,
    "cpm": round((35.38 / 742) * 1000, 2),
    "ctr": round((17 / 742) * 100, 2),
    "cpc": round(35.38 / 17, 2),
    "leads": 15,
    "cost_per_lead": round(35.38 / 15, 2),
}

# Last 7 days (Aug 31 - Sept 6) - US CIC + Thunderdome combined
# US CIC: spend 306.78, impressions 1996, link_clicks 60, leads 57
# Thunderdome: spend 35.38, impressions 742, link_clicks 17, leads 15
_7d_spend = 306.78 + 35.38
_7d_impr = 1996 + 742
_7d_clicks = 60 + 17
_7d_leads = 57 + 15
weekly_ads = {
    "spend": round(_7d_spend, 2),
    "impressions": _7d_impr,
    "clicks": _7d_clicks,
    "cpm": round((_7d_spend / _7d_impr) * 1000, 2),
    "ctr": round((_7d_clicks / _7d_impr) * 100, 2),
    "cpc": round(_7d_spend / _7d_clicks, 2),
    "leads": _7d_leads,
    "cost_per_lead": round(_7d_spend / _7d_leads, 2),
}

# Last 30 days (Aug 8 - Sept 6) - US CIC + UK CIC + Thunderdome combined
# US CIC: spend 2517.40, impressions 19186, link_clicks 614, leads 497
# UK CIC: spend 8857.94, impressions 213147, link_clicks 4546, leads 3520
# Thunderdome: spend 35.38, impressions 742, link_clicks 17, leads 15
_30d_spend = 2517.40 + 8857.94 + 35.38
_30d_impr = 19186 + 213147 + 742
_30d_clicks = 614 + 4546 + 17
_30d_leads = 497 + 3520 + 15
monthly_ads = {
    "spend": round(_30d_spend, 2),
    "impressions": _30d_impr,
    "clicks": _30d_clicks,
    "cpm": round((_30d_spend / _30d_impr) * 1000, 2),
    "ctr": round((_30d_clicks / _30d_impr) * 100, 2),
    "cpc": round(_30d_spend / _30d_clicks, 2),
    "leads": _30d_leads,
    "cost_per_lead": round(_30d_spend / _30d_leads 2),
}

# =============================================================
# WISTIA DATA (pulled from Wistia Stats API)
# ============================================================
# Media: fsx8yduvoy ("CiC VSL 2.0"), duration 820.76s
# Stats API returns all-time cumulative (no date range filter)
wistia_stats = {
    "page_loads": 213,
    "visitors": 176,
    "plays": 23,
    "play_rate": 12.5,
    "avg_percent_watched": 22.19,
    "hours_watched": 1.16,
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
print("PUSHING DATA TO DASHBOARD")
print(f"URL: {DASHBOARD_URL}")
print("=" * 60)

# Push ads data for all three timeframes
print("\n--- META ADS ---")
push("daily", "ads", daily_ads)
push("weekly", "ads", weekly_ads)
push("monthly", "ads", monthly_ads)

# Push Wistia/funnel data for all three timeframes
print("\n--- WISTIA (FUNNEL) ---")
push("daily", "funnel", wistia_stats)
push("weekly", "funnel", wistia_stats)
push("monthly", "funnel", wistia_stats)

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)

# Print summary
print("\nSUMMARY:")
print(f"  Daily:   spend £{daily_ads['spend']}, impr {daily_ads['impressions']}, CPM £{daily_ads['cpm']}, CTR {daily_ads['ctr']}%, leads {daily_ads['leads']}, CPL £{daily_ads['cost_per_lead']}")
print(f"  Weekly:  spend £{weekly_ads['spend']}, impr {weekly_ads['impressions']}, CPM £{weekly_ads['cpm']}, CTR {weekly_ads['ctr']}%, leads {weekly_ads['leads']}, CPL £{weekly_ads['cost_per_lead']}")
print(f"  Monthly: spend £{monthly_ads['spend']}, impr {monthly_ads['impressions']}, CPM £{monthly_ads['cpm']}, CTR {monthly_ads['ctr']}%, leads {monthly_ads['leads']}, CPL £{monthly_ads['cost_per_lead']}")
print(f"\n  Wistia:  loads {wistia_stats['page_loads']}, visitors {wistia_stats['visitors']}, plays {wistia_stats['plays']}, play rate {wistia_stats['play_rate']}%, avg watch {wistia_stats['avg_percent_watched']}%")
