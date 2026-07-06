# GEO/AEO Tracker — Production Deployment Runbook

Stand up the citation tracker so the platform can measure AI visibility (ChatGPT, Perplexity, Google AI Overviews, and more). Until this is done, all citation KPIs, gap analysis, and the citation-gap topic source stay empty.

**How it fits together:**

```
Axxiom backend (Railway)                    Tracker (this runbook)              Bright Data
run_citation_audit (1st & 15th, 8am CT) ──► POST /api/scrape ─────────────────► AI engine scrapers
  30 queries × engines × samples per brand    {provider, prompt}                 (ChatGPT, Perplexity, …)
  ◄── citation_records (your database) ◄──── {answer, sources[]} ◄──────────────┘
```

The tracker is a separate open-source Next.js app ([danishashko/geo-aeo-tracker](https://github.com/danishashko/geo-aeo-tracker), MIT). Bright Data keys live in the **tracker's** env, never in the Axxiom backend.

---

## Prerequisites

- [ ] GitHub account (to fork the tracker repo)
- [ ] Vercel **or** Railway account (tracker hosting — Railway recommended since the backend already lives there)
- [ ] Bright Data account with billing enabled — [brightdata.com](https://brightdata.com/)
- [ ] Access to the Axxiom backend's Railway variables

**Cost expectation:** tracker software is free; Bright Data charges ~$0.01–0.05 per scrape. At default settings (5 brands × ~30 queries × 3 engines × 3 samples, twice a month) that's ≈ 2,700 scrapes ≈ **$27–135/month**. Knobs to reduce this are in [Cost controls](#cost-controls).

---

## Step 1 — Bright Data setup

1. [ ] Create the account and add a payment method.
2. [ ] In the Bright Data dashboard: **Scrapers Library** → enable the AI scrapers for each engine you want. Start with **Perplexity**, **ChatGPT**, and **Google AI Overviews** (they match the backend default `GEO_AEO_PROVIDERS=perplexity,chatgpt,google_ai`).
3. [ ] Copy the **API key** and each scraper's **dataset ID** — you'll paste these into the tracker's env in Step 2.

## Step 2 — Deploy the tracker app

Fork or clone the upstream repo first:

```bash
git clone https://github.com/danishashko/geo-aeo-tracker.git
```

### Option A — Railway (recommended: same place as the backend)

1. [ ] Push your fork to GitHub, then in Railway: **New Service → Deploy from GitHub repo** → select the fork.
2. [ ] Build config (matches `geo-aeo-tracker/railway.toml` in this repo): Nixpacks builder, start command `npm run start -- -p $PORT`, health-check path `/`.
3. [ ] Set service **Variables**: `BRIGHT_DATA_KEY` plus one `BRIGHT_DATA_DATASET_<MODEL>` per enabled engine — exact variable names are in the tracker repo's `.env.example`.
4. [ ] Deploy and note the public URL, e.g. `https://geo-aeo-tracker-production.up.railway.app`.

### Option B — Vercel (upstream's default path)

1. [ ] Import the fork at vercel.com → framework auto-detects Next.js.
2. [ ] Add the same env vars (`BRIGHT_DATA_KEY` + dataset IDs) in Project Settings → Environment Variables.
3. [ ] Deploy and note the URL, e.g. `https://your-tracker.vercel.app`.

> **Keep the URL private.** The tracker's `/api/scrape` endpoint has no authentication — anyone who knows the URL can spend your Bright Data credits. Don't link it anywhere public; check the upstream README for an auth option before wider exposure.

## Step 3 — Smoke-test the tracker standalone

The backend health-checks `GET /` and calls `POST /api/scrape`. Verify both by hand:

```bash
TRACKER=https://your-tracker-url

# 1. Health: must return a page (anything below HTTP 500)
curl -s -o /dev/null -w "%{http_code}\n" "$TRACKER/"

# 2. One real scrape (costs one Bright Data credit, takes up to ~2 min)
curl -s -X POST "$TRACKER/api/scrape" \
  -H "Content-Type: application/json" \
  -d '{"provider": "perplexity", "prompt": "best elevator maintenance company", "requireSources": true}'
```

- [ ] Expected: JSON containing `answer` (text) and `sources` (array of URLs). An `error` field means the Bright Data key/dataset ID for that provider is wrong.

## Step 4 — Point the Axxiom backend at it

In the **backend's** Railway variables (not the tracker's):

```env
CITATION_PROVIDER=geo_aeo
GEO_AEO_TRACKER_URL=https://your-tracker-url
GEO_AEO_PROVIDERS=perplexity,chatgpt,google_ai
GEO_AEO_CONCURRENCY=2
CITATION_SAMPLE_RUNS=3
```

- [ ] Redeploy/restart the backend so settings reload.

**First-audit tip:** for a cheap end-to-end test, temporarily set `GEO_AEO_PROVIDERS=perplexity` and `CITATION_SAMPLE_RUNS=1` — a full 5-brand audit then costs ~150 scrapes (≈ $1.50–8) instead of ~1,350. Restore the full settings once verified.

## Step 5 — End-to-end verification

1. [ ] `python backend/scripts/verify_rollout.py` — the citation-provider line should print `[OK] … available`.
2. [ ] Dashboard → **Citations** → **Run audit** (or `POST /api/citations/audit`). Response should be `{"status": "audit_started"}` — if it says `unavailable`, the backend can't reach the tracker (check `GEO_AEO_TRACKER_URL` and the tracker's health).
3. [ ] Wait a few minutes per brand (each query×engine×sample is one scrape with a 120s ceiling; the backend runs 2 at a time and retries each scrape twice).
4. [ ] Citations page fills with per-query results (cited / mentioned / visibility %); dashboard citation KPIs and the Gap Analysis table populate.
5. [ ] Slack (if `SLACK_WEBHOOK_URL` set): "Bi-weekly citation audit complete."
6. [ ] From then on it runs automatically on the **1st & 15th at 8:00am Central**, and newly found gaps feed Monday's automated topic discovery.

---

## Cost controls

| Knob (backend env) | Default | Effect |
|---|---|---|
| `GEO_AEO_PROVIDERS` | `perplexity,chatgpt,google_ai` | Each engine multiplies cost. Valid: `chatgpt, perplexity, copilot, gemini, google_ai, grok` |
| `CITATION_SAMPLE_RUNS` | `3` | Samples per query×engine (3 → probabilistic visibility %; 1 → cheapest, binary) |
| `GEO_AEO_CONCURRENCY` | `2` | Parallel scrapes — affects audit speed, not cost |
| Brand `target_queries` (Brand Settings) | — | Extra custom queries add scrapes (cap: 30 queries/brand/audit) |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Notification: "Citation audit skipped — tracker unavailable" | Backend can't reach `GEO_AEO_TRACKER_URL` (wrong URL, tracker down, or `GET /` erroring). |
| Audit trigger returns `status: unavailable` | Same as above — fix reachability, retry. |
| Error: "Tracker returned no results (is it running with Bright Data keys?)" | Tracker is up but every scrape failed — wrong `BRIGHT_DATA_KEY`/dataset IDs, or Bright Data credit exhausted. Test with the Step 3 curl. |
| Some engines return results, one always empty | That engine's dataset ID is missing/wrong in the tracker env, or its scraper isn't enabled in Bright Data. |
| Audit very slow | Expected: scrapes take up to 2 min each at concurrency 2. Raise `GEO_AEO_CONCURRENCY` cautiously. |
| Failures after launch | Worker errors post to Slack and the in-app Notifications feed with the reason attached. |

## Rollback / pause

Set `CITATION_PROVIDER=none` in the backend and restart — audits stop cleanly (no failure alerts), existing citation data stays visible. Flip back to `geo_aeo` anytime.
