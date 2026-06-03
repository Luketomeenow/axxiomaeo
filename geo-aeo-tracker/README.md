# GEO/AEO Tracker (local sidecar)

The Axxiom backend uses [GEO/AEO Tracker](https://github.com/danishashko/geo-aeo-tracker) for AI citation audits via `POST /api/scrape`.

The tracker is a **separate Next.js app**. Bright Data API keys live in the **tracker** `.env`, not in the FastAPI backend.

## 1. Clone and install

```powershell
cd e:\Luke\Clients\Axxiom\axxiomaeo
git clone https://github.com/danishashko/geo-aeo-tracker.git geo-aeo-tracker-app
cd geo-aeo-tracker-app
npm install
```

Or clone anywhere and set `GEO_AEO_TRACKER_URL` to that instance.

## 2. Configure Bright Data

1. Create account at [brightdata.com](https://brightdata.com/)
2. In Bright Data → **Scrapers Library** → enable AI scrapers for the models you need
3. Copy dataset IDs for ChatGPT, Perplexity, Google AI, etc.
4. Copy `.env.example` → `.env` and fill in `BRIGHT_DATA_KEY` + dataset IDs

Minimum for backend defaults (`perplexity,google_ai`):

- `BRIGHT_DATA_DATASET_PERPLEXITY`
- `BRIGHT_DATA_DATASET_GOOGLE_AI`

## 3. Run the tracker

```powershell
npm run dev
```

Open http://localhost:3000 — validate with:

```powershell
npm run test:scraper
```

## 4. Point the Axxiom backend at it

In `backend/.env`:

```env
CITATION_PROVIDER=geo_aeo
GEO_AEO_TRACKER_URL=http://localhost:3000
GEO_AEO_PROVIDERS=perplexity,google_ai
GEO_AEO_CONCURRENCY=2
```

Restart FastAPI, then trigger an audit from the dashboard **Citations** page or wait for the bi-weekly worker.

## Providers

Comma-separated list matching the tracker API:

`chatgpt`, `perplexity`, `copilot`, `gemini`, `google_ai`, `grok`

More providers = more Bright Data usage. Start with 1–2 for cost control.

## Deploy

Deploy the tracker to Vercel (see upstream README) and set:

```env
GEO_AEO_TRACKER_URL=https://your-tracker.vercel.app
```

## Cost note

GEO/AEO Tracker software is free (MIT). Bright Data charges per scrape — budget ~$0.01–0.05 per query per model.
