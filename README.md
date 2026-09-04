# Funnel Tracking Dashboard

Live funnel tracking dashboard with webhook receiver for Zapier automation.

## Files

| File | Purpose |
|------|--------|
| `webhook_server.py` | Flask server that serves the dashboard and receives Zapier webhooks |
| `dashboard.html` | The dashboard UI (auto-served by the server) |
| `dashboard_data.json` | Data file (auto-updated by webhooks, don't edit manually) |
| `requirements.txt` | Python dependencies |
| `Procfile` | Deployment command for Render/Railway |
| `render.yaml` | Render deployment config |
| `ZAPIER_SETUP_GUIDE.md` | Step-by-step guide for wiring up Zapier zaps |

## Deploy to Render (Simplest Route)

1. Push these files to a GitHub repo
2. Go to render.com → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects the `render.yaml` config
5. Click Deploy
6. You get a public URL like `https://funnel-dashboard-xxxx.onrender.com`
7. Your dashboard is at that URL
8. Your webhook is at `https://funnel-dashboard-xxxx.onrender.com/webhook`

## Deploy to Railway

1. Go to railway.app → New Project → Deploy from GitHub
2. Select your repo
3. Railway auto-detects Python + Flask
4. Click Deploy
5. You get a public URL automatically

## Local Development

```bash
pip install -r requirements.txt
python webhook_server.py
# Dashboard at http://localhost:5000
# Webhook at http://localhost:5000/webhook
```

## Webhook Payload Format

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

Categories: `ads`, `funnel`, `sales`, `closers`, `setters`
Timeframes: `daily`, `weekly`, `monthly`

The server auto-calculates all derived metrics (CPM, CTR, show rate, close rate, ROAS, etc.) from raw inputs.
