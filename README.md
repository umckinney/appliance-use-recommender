# FlowShift

Carbon-aware appliance scheduling for your home. FlowShift recommends the best time to run high-energy appliances based on real-time grid carbon intensity, utility time-of-use rates, and your solar generation — then surfaces those recommendations through Siri.

> **Carbon data coverage:** Real-time carbon intensity currently uses BPA (Bonneville Power Administration), which covers the Pacific Northwest grid. Users outside this region will see national EIA fuel-mix data as a proxy. Expansion to other grid operators is planned.

## Features

- Real-time grid carbon intensity via BPA (Pacific Northwest)
- EIA hourly fuel-type data for accurate 48-hour carbon forecasting
- Utility TOU rate scheduling (Seattle City Light; extensible)
- Solar generation integration — live via SolarEdge or estimated via pvlib clear-sky model
- Multi-hour cycle scoring: optimizer averages cost and carbon across the full cycle span, not just the start hour
- ENERGY STAR certified model lookup for dishwashers, washers, and dryers — auto-fills per-cycle kWh from the official dataset
- Weighted cost/carbon optimizer with natural-language recommendations
- Siri/HomePod voice query support via Apple Shortcuts
- 24-hour scheduling timeline with overlap warnings for multiple appliances
- Account recovery: retrieve your API key by email

## Architecture

```
Browser / Siri
      │
      ▼
Next.js frontend (Vercel)
      │  REST
      ▼
FastAPI backend (Fly.io)
      │
      ├── PostgreSQL (Fly Postgres)
      │
      ├── BPA  ──────────── real-time carbon intensity
      ├── EIA  ──────────── 48h fuel-type carbon forecast
      ├── ENERGY STAR ───── certified appliance model data (bulk cache)
      ├── SolarEdge ─────── live solar generation (optional)
      ├── pvlib ─────────── clear-sky solar estimate (fallback)
      └── Nominatim ─────── address geocoding (OpenStreetMap)
```

## Quick Start (local dev)

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env        # fill in at least EIA_API_KEY (see table below)
uvicorn backend.main:app --reload --port 8000
```

SQLite is used locally — the database is created automatically on first run. No migration step needed for local dev.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Visit `http://localhost:3000` to onboard and get your API key.

## API Keys

| Key | Required | Where to get it | Notes |
|-----|----------|-----------------|-------|
| `EIA_API_KEY` | Recommended | [api.eia.gov](https://api.eia.gov/) — free, instant | Without it, carbon forecasting falls back to BPA flat-repeat |
| `DATABASE_URL` | Yes (prod) | Fly.io Postgres URL | SQLite used automatically in local dev |
| `SOLAREDGE_API_KEY` | No | SolarEdge monitoring portal → Admin → API Access | Only needed if you have a SolarEdge inverter |
| `SOLAREDGE_SITE_ID` | No | Same portal, or URL of your monitoring dashboard | Pair with `SOLAREDGE_API_KEY` |
| `SECRET_KEY` | Yes (prod) | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` | Change from default in any non-local deployment |

## Environment Variables

**Backend (`.env`)**

```
DATABASE_URL=sqlite+aiosqlite:///./flowshift.db   # SQLite default; override for Postgres
EIA_API_KEY=your_eia_key
SECRET_KEY=change-me-in-production
SOLAREDGE_SITE_ID=                                # optional
SOLAREDGE_API_KEY=                                # optional
```

**Frontend (`.env.local`)**

```
NEXT_PUBLIC_API_URL=http://localhost:8000         # set to your Fly.io URL in production
```

## Deployment

### Backend (Fly.io)

```bash
# 1. Install Fly CLI: https://fly.io/docs/hands-on/install-flyctl/
fly auth login

# 2. Create app and Postgres cluster
fly launch --no-deploy         # creates fly.toml; choose a region
fly postgres create --name flowshift-db --region sea

# 3. Attach database and set secrets
fly postgres attach flowshift-db
fly secrets set \
  EIA_API_KEY=your_eia_key \
  SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")

# Optional — SolarEdge
fly secrets set SOLAREDGE_SITE_ID=your_site_id SOLAREDGE_API_KEY=your_api_key

# 4. Deploy
fly deploy

# 5. Run database migrations (required on first deploy and after schema changes)
fly ssh console -C "alembic upgrade head"
```

After the first deploy, subsequent `fly deploy` runs update the app automatically. Re-run `alembic upgrade head` after any schema-changing commit.

### Frontend (Vercel)

1. Push this repo to GitHub.
2. Import it at [vercel.com/new](https://vercel.com/new). Set **Root Directory** to `frontend`.
3. Add environment variable:
   ```
   NEXT_PUBLIC_API_URL=https://<your-fly-app>.fly.dev
   ```
4. Deploy. Vercel auto-deploys on every push to `main`.

## Siri Setup (iOS 17+)

After deploying to Fly.io, the onboarding screen generates a ready-to-use Siri URL for each appliance. To create a Siri Shortcut:

1. Open the **Shortcuts** app on your iPhone.
2. Tap **+** → **Add Action** → search "URL" → select **Get contents of URL**.
3. Paste your FlowShift URL — e.g. `https://your-app.fly.dev/recommend/dishwasher?api_key=<your-key>`. The onboarding screen has a copy button for each appliance.
4. Tap **+** → **Add Action** → search "dictionary" → select **Get Dictionary from Input**.
5. Tap **+** → **Add Action** → search "dictionary" → select **Get Dictionary Value** → set Key to **text**.
6. Tap **+** → **Add Action** → search "speak" → select **Speak Text**.
7. Rename the shortcut to **Should I run the dishwasher?** (or whichever appliance).
8. Say "Hey Siri, should I run the dishwasher?"

The shortcut calls the deployed API directly, so it works from anywhere — home, office, or on cellular.

## API Reference

All authenticated endpoints accept the API key as either:
- Query parameter: `?api_key=<key>`
- HTTP header: `Authorization: Bearer <key>`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/onboard` | — | Create account; returns `api_key` |
| `POST` | `/account/lookup` | — | Retrieve `api_key` by email |
| `GET` | `/appliances/presets` | — | List default appliance presets |
| `GET` | `/appliances/brands?category=` | — | Unique brands in ENERGY STAR dataset (dishwasher / washer / dryer) |
| `GET` | `/appliances/models?category=&brand=` | — | All ENERGY STAR models for a brand |
| `GET` | `/appliances/search?category=&q=` | — | Search ENERGY STAR models by query |
| `GET` | `/appliances` | Yes | List user's appliances |
| `POST` | `/appliances` | Yes | Add or update an appliance |
| `DELETE` | `/appliances/{slug}` | Yes | Remove an appliance |
| `GET` | `/status` | Yes | Current carbon intensity + utility rate |
| `GET` | `/forecast` | Yes | 48-hour carbon + rate + solar forecast |
| `GET` | `/recommend/{slug}` | Yes | Best run windows for an appliance |

Interactive API docs are available at `/docs` (Swagger) and `/redoc` when the backend is running.

## Rate Limits

To keep the shared deployment usable for everyone:

| Endpoint | Limit |
|----------|-------|
| `POST /onboard` | 5 per hour per IP |
| `POST /account/lookup` | 10 per hour per IP |
| `GET /appliances/brands` | 30 per hour per IP |
| `GET /recommend/{slug}` | 60 per hour per API key |

Self-hosters can remove or adjust these limits in [`backend/limiter.py`](backend/limiter.py).

## Data Sources

| Source | Data | License |
|--------|------|---------|
| [BPA](https://www.bpa.gov/energy-and-services/power/wind-and-hydro-power-data) | Real-time grid carbon intensity (Pacific Northwest) | Public domain |
| [EIA](https://www.eia.gov/opendata/) | Hourly fuel-type generation by balancing authority | Public domain |
| [ENERGY STAR](https://www.energystar.gov/productfinder/product/certified-residential-dishwashers/) | Certified appliance energy data | Public domain (EPA) |
| [Nominatim / OpenStreetMap](https://nominatim.org/) | Address geocoding | ODbL |
| [pvlib](https://pvlib-python.readthedocs.io/) | Clear-sky solar irradiance model | BSD-3 |
| [SolarEdge](https://developers.solaredge.com/) | Live inverter power output | Proprietary (user's own account) |

## Contributing

Contributions are welcome. A few guidelines:

- **Tests first.** Run `pytest` before and after your change. New behavior should have a test.
- **Format.** Run `black backend/` and `ruff check backend/ --fix` before committing.
- **Migrations.** If you change a SQLAlchemy model, generate a migration: `alembic revision --autogenerate -m "describe change"` and commit it alongside the model change.
- **No hot-take PRs.** Open an issue first for anything beyond a bug fix so we can discuss approach before you invest time in it.

## License

MIT — see [LICENSE](LICENSE).
