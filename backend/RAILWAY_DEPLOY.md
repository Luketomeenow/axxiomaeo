# Railway deployment — Axxiom AEO backend

Deploy the FastAPI backend to Railway using **Supabase PostgreSQL** (`aeo` schema) for data and the same Supabase project for auth.

## Prerequisites

1. GitHub repo pushed: `https://github.com/Luketomeenow/axxiomaeo`
2. Supabase `aeo` schema applied — run [`migrations/aeo_schema.sql`](migrations/aeo_schema.sql) in Supabase SQL Editor
3. Supabase database password from **Project Settings → Database**

## 1. Create Railway project

1. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Select `Luketomeenow/axxiomaeo`
3. Set **Root Directory** to `backend`
4. Railway reads [`railway.toml`](railway.toml) automatically

**Do not** add Railway PostgreSQL — use Supabase for the database.

## 2. Environment variables

Copy from local [`backend/.env`](.env) (never commit `.env`). Required:

| Variable | Value |
|----------|--------|
| `DATABASE_URL` | `postgresql://postgres:PASSWORD@db.cdlssoeqqfrgckpxewhn.supabase.co:5432/postgres` |
| `DB_SCHEMA` | `aeo` |
| `SUPABASE_URL` | `https://cdlssoeqqfrgckpxewhn.supabase.co` |
| `SUPABASE_JWT_SECRET` | From Supabase → Project Settings → API → JWT Secret |
| `ENVIRONMENT` | `production` |
| `CORS_ORIGINS` | `https://YOUR-NETLIFY-URL.netlify.app,http://localhost:5173` |
| `ANTHROPIC_API_KEY` | Claude API key |
| `FRONTEND_URL` | Netlify dashboard URL |
| `WP_APP_PASSWORD_*` | WordPress app passwords (8 brands) |
| `WP_USERNAME_*` | WordPress usernames per brand |

Optional: `GOOGLE_SERVICE_ACCOUNT_JSON`, `SLACK_WEBHOOK_URL`, `BING_API_KEY`

Citation monitoring (GEO/AEO Tracker sidecar):

| Variable | Value |
|----------|--------|
| `CITATION_PROVIDER` | `none` until tracker is deployed, then `geo_aeo` |
| `GEO_AEO_TRACKER_URL` | Deployed tracker URL (e.g. second Railway service) |
| `GEO_AEO_PROVIDERS` | `perplexity,google_ai` |
| `WEEKLY_CONTENT_BATCH_SIZE` | Queue items processed each Monday (default `5`) |

See [backend/.env.production.example](.env.production.example) for a full Railway template.
Bright Data keys go in the **tracker** app env, not Railway backend. See [geo-aeo-tracker/README.md](../geo-aeo-tracker/README.md).

## 3. Deploy and verify

1. Trigger deploy (push to `main` or manual deploy)
2. Open Railway **Settings → Networking → Generate Domain**
3. Health check: `GET https://YOUR-RAILWAY-URL/health` should return `"database": "connected"`
4. Update Netlify env: `VITE_API_URL=https://YOUR-RAILWAY-URL`

## 4. Local smoke test (before or after deploy)

```powershell
cd backend
venv\Scripts\activate
# Set DATABASE_URL in .env first
uvicorn app.main:app --port 8000
python scripts/smoke_test.py
```

## Workers

APScheduler cron jobs run in the same Railway process (no separate worker service):

- Monday 9am CT — content generation
- 1st & 15th 8am CT — citation audit
- 1st 7am CT — schema validation
- Last day 11pm CT — monthly report

Ensure the Railway service stays **always on** (not serverless sleep) so cron fires reliably.
