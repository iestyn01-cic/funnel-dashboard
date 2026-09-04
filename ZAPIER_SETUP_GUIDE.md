# Zapier Webhook Setup Guide
## Funnel Tracking Dashboard

Your dashboard is live and the webhook receiver is running. This guide walks you through setting up each Zapier zap to feed data into the dashboard automatically.

---

## YOUR URLS

| Endpoint | URL |
|----------|-----|
| Dashboard | https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/ |
| Webhook (POST data here) | https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook |
| Status Check | https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook/status |
| Reset Data | https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook/reset |

---

## HOW THE WEBHOOK WORKS

Every Zapier zap sends a POST request to your webhook URL with this JSON structure:

```json
{
  "timeframe": "daily",
  "category": "ads",
  "data": {
    "spend": 500,
    "impressions": 45000,
    "link_clicks": 900,
    "leads": 45
  }
}
```

The server merges this data into your dashboard JSON file and auto-calculates all derived metrics (CTR, CPM, show rate, close rate, ROAS, cost per call, etc.). You only send raw numbers. The server does the math.

---

## ZAP 1: Meta Ads Data (Daily)

**Purpose:** Pull yesterday's ad spend, impressions, clicks, and leads from Facebook/Meta Ads.

**Trigger:** Schedule by Zapier
- Set to run daily at 9:00 AM your time
- This pulls the previous day's data

**Action 1:** Facebook Ads (or Facebook Lead Ads) - Find Ad Account Insights
- Select your ad account
- Date preset: Yesterday
- Fields to pull: spend, impressions, link_clicks, leads (or form submissions)

**Action 2:** Webhooks by Zapier - POST
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook
- Payload Type: JSON
- Data:
  - timeframe: daily
  - category: ads
  - data (as an object):
    - spend: (map from Facebook Ads spend)
    - impressions: (map from Facebook Ads impressions)
    - link_clicks: (map from Facebook Ads link_clicks)
    - leads: (map from Facebook Ads leads or form submissions)

**In Zapier, the JSON payload looks like:**
```json
{
  "timeframe": "daily",
  "category": "ads",
  "data": {
    "spend": "{{spend}}",
    "impressions": "{{impressions}}",
    "link_clicks": "{{link_clicks}}",
    "leads": "{{leads}}"
  }
}
```

The server auto-calculates: CPM, Link CTR, CPC, Cost Per Lead.

---

## ZAP 2: GHL Call Bookings (Real-Time)

**Purpose:** Every time someone books a call through your GHL funnel, push it to the dashboard.

**Trigger:** GoHighLevel - New Appointment Booked (or New Opportunity Created)

**Action:** Webhooks by Zapier - POST
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook
- Payload Type: JSON
- Data:
  - timeframe: daily
  - category: funnel
  - data:
    - calls_booked: 1 (increment by 1 per booking)
    - form_submissions: 1 (if they filled a form first)

**Note:** If GHL sends the total count rather than incrementing, send the total. The server merges by overwriting, so send cumulative numbers if your zap runs on a schedule, or send +1 increments if it fires per-event.

For per-event zaps (fires on each booking), use this approach instead:
- Set up a Zapier Storage (or Google Sheets) step to track the running count
- Then send the cumulative number to the webhook

---

## ZAP 3: GHL Call Dispositions (Real-Time)

**Purpose:** When a closer marks a call as showed, closed, or no-show, update the dashboard.

**Trigger:** GoHighLevel - Appointment Status Changed (or Opportunity Stage Changed)

**Action:** Webhooks by Zapier - POST
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook
- Payload Type: JSON

**For showed calls:**
```json
{
  "timeframe": "daily",
  "category": "sales",
  "data": {
    "calls_showed": "{{cumulative_showed_count}}"
  }
}
```

**For closed deals:**
```json
{
  "timeframe": "daily",
  "category": "sales",
  "data": {
    "calls_closed": "{{cumulative_closed_count}}",
    "revenue_collected": "{{cumulative_revenue}}"
  }
}
```

The server auto-calculates: Show Rate, Close Rate, AOV.

---

## ZAP 4: Payment / Revenue (Real-Time)

**Purpose:** Track cash collected the moment a payment hits.

**Trigger:** Stripe - New Charge (or your payment processor's trigger)

**Action:** Webhooks by Zapier - POST
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook
- Payload Type: JSON
- Data:
  - timeframe: daily
  - category: sales
  - data:
    - revenue_collected: (map from Stripe amount)

---

## ZAP 5: Closer Performance (Daily or Weekly)

**Purpose:** Track each closer's individual stats for the monthly table.

**Trigger:** Schedule by Zapier (daily at 6 PM) or GHL trigger

**Action:** Webhooks by Zapier - POST
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook
- Payload Type: JSON
- Data:
  - timeframe: monthly
  - category: closers
  - data:
    - name: (closer's name)
    - calls_booked: (their total booked)
    - calls_showed: (their total showed)
    - calls_closed: (their total closed)
    - revenue_collected: (their total revenue)

The server auto-calulates each closer's show rate and close rate.

---

## ZAP 6: Setter Performance (Daily or Weekly)

**Purpose:** Track each setter's outreach and booking stats.

**Trigger:** Schedule by Zapier (daily at 6 PM) or GHL trigger

**Action:** Webhooks by Zapier - POST
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook
- Payload Type: JSON
- Data:
  - timeframe: monthly
  - category: setters
  - data:
    - name: (setter's name)
    - outreach_sent: (messages/calls sent)
    - calls_booked: (calls they booked)

The server auto-calculates each setter's booking rate.

---

## ZAP 7: Weekly Reset (Optional)

**Purpose:** Reset daily data at the start of each day and weekly data at the start of each week.

**Trigger:** Schedule by Zapier
- Daily reset: Run at 12:01 AM every day
- Weekly reset: Run at 12:01 AM every Monday

**Action:** Webhooks by Zapier - POST
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook/reset
- Payload Type: JSON
- Data:
  - timeframe: daily (for daily reset) or weekly (for weekly reset)

---

## ZAP 8: Slack Daily Summary (Optional)

**Purpose:** Post a daily summary to your Slack channel.

**Trigger:** Schedule by Zapier (daily at 6 PM)

**Action 1:** Webhooks by Zapier - GET
- URL: https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/dashboard_data.json
- This pulls the current dashboard data

**Action 2:** Slack - Send Message
- Channel: your team channel
- Message text: Format the daily numbers (spend, leads, calls booked, calls showed, calls closed, revenue) into a Slack message

---

## TESTING YOUR WEBHOOK

After setting up each zap, test it by sending a manual POST:

**Using curl (terminal):**
```bash
curl -X POST https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "timeframe": "daily",
    "category": "ads",
    "data": {
      "spend": 500,
      "impressions": 45000,
      "link_clicks": 900,
      "leads": 45
    }
  }'
```

**Using Zapier's built-in test:**
Every Webhooks by Zapier action has a "Test" button. Click it after configuring your payload to send a test request. You should see a success response.

**Verify on the dashboard:**
Open https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/ and check the Daily tab. Your test data should appear within 60 seconds.

---

## WHAT THE SERVER AUTO-CALCULATES

You only need to send these raw numbers. The server computes everything else:

**Ads (send these):** spend, impressions, link_clicks, leads
**Server calculates:** CPM, Link CTR, CPC, Cost Per Lead

**Funnel (send these):** page_views, form_submissions, calls_booked
**Server calculates:** Page Conversion Rate, Booking Rate

**Sales (send these):** calls_booked, calls_showed, calls_closed, revenue_collected
**Server calculates:** Show Rate, Close Rate, AOV

**Keystone (fully automatic):** ROAS, Cost Per Booked Call, Cost Per Showed Call, Cost Per Closed Deal, Collected Per Booked Call, Collected Per Showed Call

**Closers/Setters (send these):** name, calls_booked, calls_showed, calls_closed, revenue_collected
**Server calculates:** Show Rate, Close Rate per person

---

## TROUBLESHOOTING

**Webhook returns 400:** Check your JSON structure. Make sure timeframe, category, and data are all present.

**Webhook returns 401:** You have AUTH_TOKEN enabled. Add "auth_token" to your payload.

**Dashboard shows zeros:** The server is running but no data has been sent yet. Test with the curl command above.

**Dashboard not loading:** Check the server status at https://5000-f7116517-9d5c-4805-94ef-fe3a20cd.daytonaproxy01.net/webhook/status

**Data not updating:** The dashboard auto-refreshes every 60 seconds. Hard refresh your browser if needed.

---

## SECURITY NOTE

The webhook URL is currently public with no auth token. For production use, set an AUTH_TOKEN in webhook_server.py and include it in every Zapier payload. This prevents random POSTs from updating your dashboard.
