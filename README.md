# FlowShift

Carbon-aware appliance scheduling for your home. FlowShift recommends the best time to run high-energy appliances based on real-time grid carbon intensity, utility time-of-use rates, and your solar generation.

## Features

- Real-time grid carbon intensity via BPA (Pacific Northwest)
- EIA hourly fuel-type data for accurate 48-hour carbon forecasting
- Utility TOU rate scheduling (Seattle City Light)
- Solar generation integration (SolarEdge + pvlib clear-sky irradiance)
- Multi-hour cycle scoring: optimizer averages cost and carbon across the full cycle span, not just the start hour
- ENERGY STAR model lookup for dishwashers, washers, and dryers — auto-fills per-cycle kWh during onboarding
- Weighted cost/carbon optimizer with natural-language recommendations
- Siri/HomePod voice query support via Apple Shortcuts
- Dashboard appliance management: add and delete appliances after onboarding
- Account recovery: retrieve your API key by email on the onboarding page
- 24h scheduling timeline: toggle appliances on the dashboard to see best run windows side by side, with overlap warnings

## Quick Start

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # add your API keys
uvicorn backend.main:app --reload --port 8000 --host 0.0.0.0
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Visit `http://localhost:3000` to onboard and get your API key.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | SQLite (dev) or PostgreSQL (prod) |
| `EIA_API_KEY` | Free key from [api.eia.gov](https://api.eia.gov/) |
| `SOLAREDGE_SITE_ID` | Optional — SolarEdge site ID |
| `SOLAREDGE_API_KEY` | Optional — SolarEdge API key |
| `SECRET_KEY` | App secret (change in production) |

## Siri Setup (iOS 17+)

1. Open the **Shortcuts** app
2. Tap **+** → **Add Action** → search "URL" → tap **Get contents of URL**
3. Paste your FlowShift URL: `http://<your-mac-ip>:8000/recommend/dishwasher?api_key=<your-key>`
4. Tap **+** → **Add Action** → search "dictionary" → tap **Get Dictionary from Input**
5. Tap **+** → **Add Action** → search "dictionary" → tap **Get Dictionary Value** → set Key to **text**
6. Tap **+** → **Add Action** → search "speak" → tap **Speak Text**
7. Tap the shortcut title at the top → rename to **Should I run the dishwasher?**
8. Say "Hey Siri, should I run the dishwasher?"

The onboarding screen generates the correct URL for each appliance and includes a copy button. Both devices must be on the same Wi-Fi network. For always-available access, deploy to Fly.io and use your production URL instead.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/onboard` | Create account, returns `api_key` |
| `POST` | `/account/lookup` | Retrieve `api_key` by email |
| `GET` | `/appliances/presets` | List default appliance presets |
| `GET` | `/appliances/search?category=&q=` | Search ENERGY STAR certified models (dishwasher / washer / dryer) |
| `GET` | `/appliances` | List user's appliances (requires `api_key`) |
| `POST` | `/appliances` | Add an appliance (requires `api_key`) |
| `DELETE` | `/appliances/{slug}` | Delete an appliance (requires `api_key`) |
| `GET` | `/status` | Current carbon intensity + rate (requires `api_key`) |
| `GET` | `/forecast` | 48-hour carbon + rate forecast (requires `api_key`) |
| `GET` | `/recommend/{slug}` | Best run windows for a specific appliance (requires `api_key`) |

## Deployment

### Backend (Fly.io)

```bash
fly postgres create --name flowshift-db
fly secrets set DATABASE_URL=<postgres-url> EIA_API_KEY=<key> SECRET_KEY=<secret>
fly deploy
```

### Frontend (Vercel)

Connect the repo at [vercel.com](https://vercel.com) and set:

```
NEXT_PUBLIC_API_URL=https://<your-fly-app>.fly.dev
```

Vercel auto-deploys on every push to `main`.

## License

MIT
