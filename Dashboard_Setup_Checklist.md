# Dashboard Automation Setup Checklist

## What Was Built

1. **Live Dashboard** (`dashboard.html`) - Visual dashboard with 5 tabs: Daily, Weekly, Monthly, Bottleneck Analysis, and Setup Guide
2. **Data File** (`dashboard_data.json`) - The JSON file the dashboard reads from. All your Zapier zaps push data into this file.
3. **This Checklist** - Step by step guide to wire everything up

---

## What You Need To Do (In Order)

### STEP 1: Set Up Zap 1 - Meta Ads Data (10 min)

This pulls your ad spend, impressions, clicks, CPM, CTR, and cost per lead automatically every day.

1. Go to Zapier and create a new Zap
2. **Trigger**: Schedule by Zapier -> Every Day at 9:00 AM
3. **Action 1**: Facebook Ads for Business -> Find Ad Account Insights
   - Select your ad account
   - Set date range to "yesterday"
   - Fields to pull: spend, impressions, link clicks, cpm, ctr, cpc
4. **Action 2**: Webhooks by Zapier -> POST
   - URL: [Your dashboard webhook URL - see dashboard Setup Guide tab]
   - Payload Type: JSON
   - Data mapping:
     ```
     {
       "section": "ads",
       "period": "daily",
       "spend": {{spend}},
       "impressions": {{impressions}},
       "cpm": {{cpm}},
       "link_clicks": {{link_clicks}},
       "link_ctr": {{ctr}},
       "cpc": {{cpc}},
       "cost_per_lead": {{cost_per_lead}},
       "leads": {{leads}}
     }
     ```
5. Test the Zap and turn it on

### STEP 2: Set Up Zap 2 - GHL Call Bookings (10 min)

This fires every time someone books a call through your funnel.

1. Create a new Zap
2. **Trigger**: GoHighLevel -> New Appointment
   - Select your calendar/location
3. **Action**: Webhooks by Zapier -> POST
   - URL: [Your dashboard webhook URL]
   - Payload:
     ```
     {
       "section": "funnel",
       "period": "daily",
       "event": "call_booked",
       "setter": {{assignee_name}},
       "source": {{custom_fields.traffic_source}},
       "timestamp": {{created_at}}
     }
     ```
4. Test and turn on

### STEP 3: Set Up Zap 3 - GHL Call Dispositions (10 min)

This fires when your closers mark calls as showed, no-show, closed, or lost.

1. Create a new Zap
2. **Trigger**: GoHighLevel -> Appointment Status Changed
3. **Action**: Webhooks by Zapier -> POST
   - URL: [Your dashboard webhook URL]
   - Payload:
     ```
     {
       "section": "sales",
       "period": "daily",
       "event": "call_disposition",
       "closer": {{assignee_name}},
       "status": {{appointment_status}},
       "deal_value": {{custom_fields.deal_value}}
     }
     ```
4. Test and turn on

### STEP 4: Set Up Zap 4 - Revenue Collected (10 min)

This fires when a payment comes through.

1. Create a new Zap
2. **Trigger**: Stripe (or your payment processor) -> New Payment
3. **Action**: Webhooks by Zapier -> POST
   - URL: [Your dashboard webhook URL]
   - Payload:
     ```
     {
       "section": "sales",
       "period": "daily",
       "event": "payment",
       "amount": {{amount}},
       "customer": {{customer_name}},
       "closer": {{metadata.closer_name}}
     }
     ```
4. Test and turn on

### STEP 5: Set Up Zap 5 - Slack Daily Summary (5 min, optional but recommended)

Posts a daily EOD summary to your Slack channel.

1. Create a new Zap
2. **Trigger**: Schedule by Zapier -> Every Day at 6:00 PM
3. **Action**: Slack -> Send Message
   - Channel: Your team channel
   - Message text: Use the dashboard data to format a summary
4. Test and turn on

---

## GHL Setup Requirements

### Tag Every Lead With Traffic Source

In GHL, set up custom fields and workflows so every lead gets tagged with where they came from:
- Facebook VSL ad
- Facebook follower ad (if still running)
- Organic
- Any other source

This gives you per-channel ROAS instead of blended guessing.

### Give Each Closer a Unique Calendar Embed

Each closer gets their own booking link embedded in the funnel. This traces every deal back to the specific closer who closed it. Without this, you can't track ROAS per closer.

### Make Closers Log Dispositions

Every call must be marked in GHL as one of:
- Showed - Closed
- Showed - Lost
- No-show
- Rescheduled

This data feeds the dashboard automatically. If closers don't log dispositions, the dashboard stays blank.

---

## What Happens After Setup

Once all 5 zaps are running:

- **Daily tab** updates automatically every morning with yesterday's ad data and real-time as calls get booked and dispositions get logged
- **Weekly tab** aggregates the week's data and auto-calculates keystone metrics (ROAS, cost per booked call, collected $ per booked call)
- **Monthly tab** shows the full month with per-closer and per-setter breakdowns
- **Bottleneck Analysis tab** walks your funnel top to bottom with color-coded status indicators showing exactly which metric is contracting

The dashboard refreshes every 60 seconds. No manual data entry needed.

---

## Troubleshooting

**Dashboard shows zeros**: The zaps haven't fired yet or the webhook URL is wrong. Check the Setup Guide tab in the dashboard for the correct webhook URL.

**Some metrics are blank**: The corresponding zap isn't set up yet. Each section of the dashboard only populates when its data source is connected.

**Closer table is empty**: Your closers aren't logging dispositions in GHL, or Zap 3 isn't configured correctly.

**Setter table is empty**: Your setters aren't logging bookings in GHL, or Zap 2 isn't configured correctly.

**Ad data not updating**: Check that your Facebook Ads connection in Zapier has the right permissions and the correct ad account is selected.
