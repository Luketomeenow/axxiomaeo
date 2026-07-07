# Axxiom AEO Automation Platform

Answer Engine Optimization automation for Axxiom Elevator's 5-brand network. Generates AEO-optimized content via Claude, manages schema markup, monitors AI citations, and publishes to WordPress — with human approval before anything goes live.

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

Local no-auth mode requires an explicit opt-in: set `AUTH_DEV_BYPASS=true` together with `ENVIRONMENT=development` and empty `SUPABASE_URL`/`SUPABASE_JWT_SECRET`. Without the flag the API always requires a valid Supabase JWT — a misconfigured deploy fails closed instead of open.

## Environment Variables

See [backend/.env.example](backend/.env.example) and [frontend/.env.example](frontend/.env.example).

Key backend variables:

- `ANTHROPIC_API_KEY` — Claude content generation
- `DATABASE_URL` — Supabase PostgreSQL connection string (see `backend/.env.example`)
- `DB_SCHEMA` — `aeo` (default)
- `WP_APP_PASSWORD_*` / `WP_USERNAME_*` — WordPress Application Password + login per brand
- `WP_AUTHOR_ID_*` — WordPress user ID to set as the post author/byline per brand (optional; 0/unset = posts belong to the application-password account)
- `PEEC_API_KEY` — Legacy Peec.ai citation monitoring (optional; use `CITATION_PROVIDER=peec`)
- `CITATION_PROVIDER` — `geo_aeo` (default), `peec`, `none`, or `auto`
- `GEO_AEO_TRACKER_URL` — URL of self-hosted [GEO/AEO Tracker](geo-aeo-tracker/README.md) ([deployment runbook](geo-aeo-tracker/DEPLOYMENT.md))
- `GEO_AEO_PROVIDERS` — Comma-separated AI models (e.g. `perplexity,google_ai`)
- `GOOGLE_SERVICE_ACCOUNT_JSON` — Base64-encoded service account for GSC + GA4
- `SUPABASE_JWT_SECRET` — JWT validation for dashboard API calls
- `SLACK_WEBHOOK_URL` — Worker notifications (optional)
- `DISCORD_WEBHOOK_URL` — Published-post notifications with live links (optional; Discord channel → Integrations → Webhooks)
- `AUTO_PUBLISH_ENABLED` — `true` (default) publishes validated drafts automatically; `false` restores the approval gate
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

### Discussion policy on published posts

Every published post (and every update) is sent with explicit `comment_status` and `ping_status`, so it never depends on a site's *Settings → Discussion* default. Both default **closed** (`WP_ALLOW_COMMENTS` / `WP_ALLOW_PINGS`) — comments off stops spam-bot comments on unattended auto-published posts; pings off avoids inbound trackback spam (`ping_status: open` does not earn backlinks — that's a separate outbound setting — and is a dead SEO/AEO signal). To retro-fit posts published before this policy: `python backend/scripts/lock_discussion.py --apply`.

## Scheduled Workers (America/Chicago)

| Job | Schedule | Behavior |
|---|---|---|
| Topic discovery | Daily 8am | Picks 1 topic/brand (default), alternating a search-demand trend pick with a citation-gap AEO pick day-to-day; falls back to coverage gaps. Deduped, source-tagged |
| Daily content | Daily 9am | Generates up to `CONTENT_GENERATION_MAX_PER_BRAND` drafts per brand; drafts that pass validation **publish automatically** (`AUTO_PUBLISH_ENABLED=true`, the default) — failed-validation drafts stop in `needs_review` |
| Citation audit | 1st & 15th, 8am | GEO/AEO Tracker audit (Perplexity, ChatGPT, Google AI by default) across all brands |
| Schema validation | 1st of month, 7am | Validates pages; queues fixes for approval |
| Content refresh | Sunday 6am | Re-publishes stale content (90+ days); re-audits gap-sourced posts |
| Monthly report | Last day, 11pm | Compiles and stores report JSON |

Rollout: [wordpress/ROLLOUT_VERIFICATION.md](wordpress/ROLLOUT_VERIFICATION.md) · Authority: [wordpress/AUTHORITY_CHECKLIST.md](wordpress/AUTHORITY_CHECKLIST.md)

## Publish Workflow (monitor-after model)

1. The daily worker generates content + schema per brand
2. Drafts that **pass validation publish to their own brand automatically** (`AUTO_PUBLISH_ENABLED=true`, the default); an audit event records `auto-publish` as the approver, and a notification with the live post links goes to the in-app feed, Slack, and Discord (`DISCORD_WEBHOOK_URL`)
3. Drafts that **fail validation stop** in `needs_review` and wait for a human
4. **Monitoring/undo:** the **Published Content** page lists everything live; **Return to Review** sets the WordPress post back to draft and pulls the item back into Content Review
5. Manually-triggered generations (dashboard Generate/Regenerate buttons) still land in **Content Review** for manual approval; schema-only deployments still require approval in **Schema Review**

Kill switch: set `AUTO_PUBLISH_ENABLED=false` in Railway to restore the approve-before-publish gate for the daily worker.

## Deploy to Railway (Backend)

See [DEPLOY.md](DEPLOY.md) for the full checklist, [backend/RAILWAY_DEPLOY.md](backend/RAILWAY_DEPLOY.md) for Railway details, [frontend/NETLIFY_DEPLOY.md](frontend/NETLIFY_DEPLOY.md) for Netlify, and [wordpress/README.md](wordpress/README.md) for WordPress schema output.

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
| POST | `/api/content/queue/from-gap` | Add gap query to content queue |
| POST | `/api/content/topics/discover` | Run topic discovery now (auto-queue demand-driven topics) |
| POST | `/api/content/published/{id}/return-to-review` | Unpublish: set live WP post to draft, return to Content Review |
| GET | `/api/reports/gsc` | GSC query highlights by brand |
| GET | `/api/reports/search-vs-generative` | Search vs. AI-generative visibility + traffic, side by side |
| POST | `/api/content/drafts/{id}/approve` | Approve + publish |
| POST | `/api/content/drafts/{id}/reject` | Reject draft |
| GET | `/api/schema/deployments` | Schema approval inbox |
| POST | `/api/schema/deployments/{id}/approve` | Deploy schema |
| GET | `/api/citations/latest` | Citation results |
| POST | `/api/citations/audit` | Trigger audit |
| GET | `/api/reports/dashboard` | Dashboard KPIs |
| GET | `/api/notifications` | In-app notifications |

Not exhaustive — see each router in `backend/app/routers/` for the full set.

## Brands (5 sites)

| ID | Name | URL |
|---|---|---|
| axxiom | Axxiom Elevator Florida | axxiomelevatorfl.com |
| ameritex | AmeriTex Elevator | ameritexelevator.com |
| arizona_es | Arizona Elevator Solutions | azelevatorsolutions.com |
| liftech | Liftech Elevator | liftechelevator.com |
| quality | Quality Elevator | qualityelevator.com |

Motion, Evolution, and IronHawk were retired from the AEO system on 2026-07-06 (`alter_aeo_v9.sql`).

## License

Proprietary — Axxiom Elevator / internal use only.
