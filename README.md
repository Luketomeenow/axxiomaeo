# Axxiom AEO Automation Platform

Answer Engine Optimization automation for Axxiom Elevator's 8-brand network. Generates AEO-optimized content via Claude, manages schema markup, monitors AI citations, and publishes to WordPress — with human approval before anything goes live.

## Architecture

| Layer | Stack | Hosting |
|---|---|---|
| Backend API + Workers | Python 3.12, FastAPI, APScheduler, SQLAlchemy | Railway |
| Frontend Dashboard | React, TypeScript, Tailwind, TanStack Query | Netlify |
| Auth | Supabase Auth (JWT) | Supabase |
| Database | PostgreSQL (`aeo` schema) | Supabase (same project as auth) |

## Repository Structure

```
axxiomaeo/
├── backend/          # FastAPI + cron workers (Railway)
├── frontend/         # React dashboard (Netlify)
└── README.md
```

## Quick Start (Local)

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys

# Requires PostgreSQL — use Supabase (recommended) or local Postgres
# See backend/.env.example for DATABASE_URL format (Supabase Session pooler or direct)
uvicorn app.main:app --reload --port 8000
```

On first startup, the API auto-creates tables and seeds brands + content queue.

Manual seed:

```bash
python -m app.utils.seed
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
# Set VITE_API_URL=http://localhost:8000
# Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY

npm run dev
```

Open http://localhost:5173

### Development Auth

If Supabase is not configured, the backend accepts requests without JWT validation in `development` mode when `SUPABASE_URL` and `SUPABASE_JWT_SECRET` are empty.

## Environment Variables

See [backend/.env.example](backend/.env.example) and [frontend/.env.example](frontend/.env.example).

Key backend variables:

- `ANTHROPIC_API_KEY` — Claude content generation
- `DATABASE_URL` — Supabase PostgreSQL connection string (see `backend/.env.example`)
- `DB_SCHEMA` — `aeo` (default)
- `WP_APP_PASSWORD_*` — WordPress Application Password per brand
- `PEEC_API_KEY` — Legacy Peec.ai citation monitoring (optional; use `CITATION_PROVIDER=peec`)
- `CITATION_PROVIDER` — `geo_aeo` (default), `peec`, `none`, or `auto`
- `GEO_AEO_TRACKER_URL` — URL of self-hosted [GEO/AEO Tracker](geo-aeo-tracker/README.md)
- `GEO_AEO_PROVIDERS` — Comma-separated AI models (e.g. `perplexity,google_ai`)
- `GOOGLE_SERVICE_ACCOUNT_JSON` — Base64-encoded service account for GSC + GA4
- `SUPABASE_JWT_SECRET` — JWT validation for dashboard API calls
- `SLACK_WEBHOOK_URL` — Worker notifications (optional)
- `FRONTEND_URL` — Deep links in Slack messages
- `CORS_ORIGINS` — Netlify URL + localhost

## WordPress Integration

Add to each brand site's `functions.php` to output schema in `<head>`:

```php
add_action('wp_head', function() {
    global $post;
    if ($schema = get_post_meta($post->ID, 'aeo_schema_json', true)) {
        echo '<script type="application/ld+json">' . $schema . '</script>';
    }
});
```

Create a WordPress Application Password for each site (Users → Profile → Application Passwords). Store in `WP_APP_PASSWORD_{BRAND_ID}` env vars.

## Scheduled Workers (America/Chicago)

| Job | Schedule | Behavior |
|---|---|---|
| Weekly content | Monday 9am | Generates draft → `pending_review` (no auto-publish) |
| Citation audit | 1st & 15th, 8am | Peec.ai audit across all brands |
| Schema validation | 1st of month, 7am | Validates pages; queues fixes for approval |
| Monthly report | Last day, 11pm | Compiles and stores report JSON |

## Approval Workflow

1. Worker or manual trigger generates content + schema
2. Draft appears in **Content Review** inbox (`pending_review`)
3. Reviewer previews HTML + JSON-LD in dashboard
4. **Approve & Publish** pushes to WordPress via REST API
5. Schema-only deployments follow the same flow in **Schema Review**

Nothing publishes to WordPress without explicit approval.

## Deploy to Railway (Backend)

See [backend/RAILWAY_DEPLOY.md](backend/RAILWAY_DEPLOY.md) for the full checklist.

1. Create Railway project, connect GitHub repo
2. Set root directory to `backend/`
3. Set env vars from `backend/.env.example` (use Supabase `DATABASE_URL`, not Railway Postgres)
4. Deploy — health check at `/health` (includes database connectivity)
5. Set Netlify `VITE_API_URL` to the Railway public URL

## Deploy to Netlify (Frontend)

1. Connect GitHub repo
2. Base directory: `frontend`
3. Build command: `npm run build`
4. Publish directory: `frontend/dist`
5. Set environment variables:
   - `VITE_API_URL` — Railway public URL
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
6. In Supabase: add Netlify URL to Auth redirect allowlist

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (no auth) |
| GET | `/api/brands` | List brands |
| GET | `/api/content/queue` | Content queue |
| GET | `/api/content/drafts` | List drafts |
| POST | `/api/content/generate` | Trigger generation |
| POST | `/api/content/drafts/{id}/approve` | Approve + publish |
| POST | `/api/content/drafts/{id}/reject` | Reject draft |
| GET | `/api/schema/deployments` | Schema approval inbox |
| POST | `/api/schema/deployments/{id}/approve` | Deploy schema |
| GET | `/api/citations/latest` | Citation results |
| POST | `/api/citations/audit` | Trigger audit |
| GET | `/api/reports/dashboard` | Dashboard KPIs |
| GET | `/api/notifications` | In-app notifications |

## Brands (8 sites)

| ID | Name | URL |
|---|---|---|
| axxiom | Axxiom Elevator | axxiomelevator.com |
| ameritex | AmeriTex Elevator | ameritexelevator.com |
| arizona_es | Arizona Elevator Solutions | azelevatorsolutions.com |
| liftech | Liftech Elevator | liftechelevator.com |
| motion | Motion Elevator Services | motionelevator.com |
| quality | Quality Elevator | qualityelevator.com |
| evolution | Evolution Elevator | evolutionelevator.com |
| ironhawk | IronHawk Elevator | ironhawkelevator.com |

Confirm Evolution and IronHawk URLs before production deploy.

## License

Proprietary — Axxiom Elevator / internal use only.
