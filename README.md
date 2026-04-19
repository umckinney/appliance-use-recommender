# FlowShift

Carbon-aware appliance scheduling for your home. FlowShift recommends the best time to run high-energy appliances based on real-time grid carbon intensity, utility time-of-use rates, and your solar generation.

## Features

- Real-time grid carbon intensity via BPA (Pacific Northwest)
- EIA hourly fuel-type data for accurate 48-hour carbon forecasting
- Utility TOU rate scheduling (Seattle City Light)
- Solar generation integration (SolarEdge + Open-Meteo irradiance)
- Weighted cost/carbon optimizer with natural-language recommendations
- Siri/HomePod voice query support via Apple Shortcuts

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

1. Open the Shortcuts app
2. Create a new shortcut → Add action → **Get contents of URL**
3. Set URL to `http://<your-mac-ip>:8000/recommend/dishwasher?api_key=<your-key>`
4. Add action → **Get Dictionary from Input** (auto-links to previous step)
5. Add action → **Get Dictionary Value** → set Key to `text`
6. Add action → **Speak Text** (auto-links to dictionary value)
7. Rename the shortcut to your trigger phrase (e.g. "Should I run the dishwasher")
8. Say "Hey Siri, should I run the dishwasher"

> Both devices must be on the same WiFi network. For always-available access, deploy to Fly.io and use your production URL instead.

## Deployment

```bash
fly deploy
```

See `fly.toml` for configuration.

## License

MIT
