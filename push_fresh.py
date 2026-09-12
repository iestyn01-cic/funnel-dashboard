#!/usr/bin/env python3
"""Push fresh Meta Ads + Wistia data to the live dashboard webhook."""
import json
import urllib.request

DASHBOARD_URL = "https://funnel-dashboard-r0f0.onrender.com/webhook"

# ============================================================
# META ADS DATA - Pulled Sept 9, 2026
# Date ranges: yesterday (Sept 8), last 7d (Sept 2-8), last 30d (Aug 10-Sept 8)
# Campaigns: Thunderdome US, Thunderdome UK, Hammer Them Retargeting UK,
#            US CIC Schedule ABO, UK CIC Schedule ABO
# ============================================================

# YESTERDAY (Sept 8) - 3 campaigns had spend
# Thunderdome US: spend 109.81, impr 736, clicks 31, link_clicks 19, leads 0
# Thunderdome UK: spend 333.31, impr 6784, clicks 199, link_clicks 129, leads 5
# Hammer Them RT UK: spend 43.10, impr 1032, clicks 26, link_clicks 15, leads 1
d_spend = 109.81 + 333.31 + 43.10
d_impr = 736 + 6784 + 1032
d_clicks = 31 + 199 + 26
d_link = 19 + 129 + 15
d_leads = 0 + 5 + 1
daily_ads = {
    "spend": round(d_spend, 2),
    "impressions": d_impr,
    "clicks": d_clicks,
    "link_clicks": d_link,
    "cpm": round((d_spend / d_impr) * 1000, 2),
    "ctr": round((d_clicks / d_impr) * 100, 2),
    "cpc": round(d_spend / d_clicks, 2),
    "leads": d_leads,
    "cost_per_lead": round(d_spend / d_leads, 2) if d_leads else 0,
}

# LAST 7 DAYS (Sept 2-8) - 5 campaigns
# Thunderdome US: spend 109.81, impr 736, clicks 31, link_clicks 19, leads 0
# Thunderdome UK: spend 605.79, impr 12418, clicks 393, link_clicks 246, leads 5
# Hammer Them RT UK: spend 43.92, impr 1048, clicks 30, link_clicks 17, leads 1
# US CIC: spend 111.28, impr 658, clicks 33, link_clicks 20, leads 0
# UK CIC: spend 170.51, impr 3296, clicks 79, link_clicks 63, leads 3
w_spend = 109.81 + 605.79 + 43.92 + 111.28 + 170.51
w_impr = 736 + 12418 + 1048 + 658 + 3296
w_clicks = 31 + 393 + 30 + 33 + 79
w_link = 19 + 246 + 17 + 20 + 63
w_leads = 0 + 5 + 1 + 0 + 3
weekly_ads = {
    "spend": round(w_spend, 2),
    "impressions": w_impr,
    "clicks": w_clicks,
    "link_clicks": w_link,
    "cpm": round((w_spend / w_impr) * 1000, 2),
    "ctr": round((w_clicks / w_impr) * 100, 2),
    "cpc": round(w_spend / w_clicks, 2),
    "leads": w_leads,
    "cost_per_lead": round(w_spend / w_leads, 2) if w_leads else 0,
}

# LAST 30 DAYS (Aug 10 - Sept 8) - 5 campaigns
# Thunderdome US: spend 109.81, impr 736, clicks 31, link_clicks 19, leads 0
# Thunderdome UK: spend 605.79, impr 12418, clicks 393, link_clicks 246, leads 5
# Hammer Them RT UK: spend 43.92, impr 1048, clicks 30, link_clicks 17, leads 1
# US CIC: spend 2399.47, impr 18110, clicks 771, link_clicks 593, leads 3
# UK CIC: spend 8031.44, impr 193852, clicks 5190, link_clicks 4172, leads 71
m_spend = 109.81 + 605.79 + 43.92 + 2399.47 + 8031.44
m_impr = 736 + 12418 + 1048 + 18110 + 193852
m_clicks = 31 + 393 + 30 + 771 + 5190
m_link = 19 + 246 + 17 + 593 + 4172
m_leads = 0 + 5 + 1 + 3 + 71
monthly_ads = {
    "spend": round(m_spend, 2),
    "impressions": m_impr,
    "clicks": m_clicks,
    "link_clicks": m_link,
    "cpm": round((m_spend / m_impr) * 1000, 2),
    "ctr": round((m_clicks / m_impr) * 100, 2),
    "cpc": round(m_spend / m_clicks, 2),
    "leads": m_leads,
    "cost_per_lead": round(m_spend / m_leads, 2) if m_leads else 0,
}

# ============================================================
# WISTIA DATA - Pulled Sept 9, 2026
# Media: fsx8yduvoy, all-time cumulative (Wistia stats API has no date filter)
# ============================================================
wistia_stats = {
    "page_loads": 822,
    "visitors": 661,
    "plays": 69,
    "play_rate": round(0.09228441754916793 * 100, 2),
    "avg_percent_watched": round(0.275696 * 100, 2),
    "hours_watched": 4.34,
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
print(f"Date: Sept 9, 2026")
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
print(f"\n  DAILY (Sept 8):")
print(f"    Spend: £{daily_ads['spend']} | Impr: {daily_ads['impressions']} | CPM: £{daily_ads['cpm']}")
print(f"    Clicks: {daily_ads['clicks']} | Link Clicks: {daily_ads['link_clicks']} | CTR: {daily_ads['ctr']}% | CPC: £{daily_ads['cpc']}")
print(f"    Leads: {daily_ads['leads']} | CPL: £{daily_ads['cost_per_lead']}")
print(f"\n  WEEKLY (Sept 2-8):")
print(f"    Spend: £{weekly_ads['spend']} | Impr: {weekly_ads['impressions']} | CPM: £{weekly_ads['cpm']}")
print(f"    Clicks: {weekly_ads['clicks']} | Link Clicks: {weekly_ads['link_clicks']} | CTR: {weekly_ads['ctr']}% | CPC: £{weekly_ads['cpc']}")
print(f"    Leads: {weekly_ads['leads']} | CPL: £{weekly_ads['cost_per_lead']}")
print(f"\n  MONTHLY (Aug 10-Sept 8):")
print(f"    Spend: £{monthly_ads['spend']} | Impr: {monthly_ads['impressions']} | CPM: £{monthly_ads['cpm']}")
print(f"    Clicks: {monthly_ads['clicks']} | Link Clicks: {monthly_ads['link_clicks']} | CTR: {monthly_ads['ctr']}% | CPC: £{monthly_ads['cpc']}")
print(f"    Leads: {monthly_ads['leads']} | CPL: £{monthly_ads['cost_per_lead']}")
print(f"\n  WISTIA (all-time cumulative):")
print(f"    Loads: {wistia_stats['page_loads']} | Visitors: {wistia_stats['visitors']} | Plays: {wistia_stats['plays']}")
print(f"    Play Rate: {wistia_stats['play_rate']}% | Avg Watch: {wistia_stats['avg_percent_watched']}% | Hours: {wistia_stats['hours_watched']}")
