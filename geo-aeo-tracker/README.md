# GEO/AEO Tracker (local sidecar)

The Axxiom backend uses [GEO/AEO Tracker](https://github.com/danishashko/geo-aeo-tracker) for AI citation audits via `POST /api/scrape`.

**Full production deployment runbook:** [DEPLOYMENT.md](DEPLOYMENT.md) — Bright Data setup, Railway/Vercel deploy, standalone smoke test, backend wiring, cost controls, troubleshooting. Start there for anything beyond local dev.

The tracker is a **separate Next.js app** — its code isn't in this repo, only this deployment config. Bright Data API keys live in the **tracker's** `.env`, never in the FastAPI backend.

## Local development

```bash
git clone https://github.com/danishashko/geo-aeo-tracker.git
cd geo-aeo-tracker
npm install
cp .env.example .env
# Fill in BRIGHT_DATA_KEY + dataset IDs — see DEPLOYMENT.md Step 1
npm run dev
```

Open http://localhost:3000 — validate with:

```bash
npm run test:scraper
```

Point a local backend at it (`backend/.env`):

```env
CITATION_PROVIDER=geo_aeo
GEO_AEO_TRACKER_URL=http://localhost:3000
GEO_AEO_PROVIDERS=perplexity,chatgpt,google_ai
```

Restart FastAPI, then trigger an audit from the dashboard **Citations** page or wait for the 1st/15th cron.

## Providers

Comma-separated list matching the tracker API: `chatgpt`, `perplexity`, `copilot`, `gemini`, `google_ai`, `grok`. More providers = more Bright Data usage — see [DEPLOYMENT.md's cost controls](DEPLOYMENT.md#cost-controls).

For production deployment, cost estimates, and troubleshooting, see [DEPLOYMENT.md](DEPLOYMENT.md).
