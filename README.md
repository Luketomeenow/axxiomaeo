# Axxiom AEO Automation Platform

Answer Engine Optimization automation for Axxiom Elevator's 5-brand network. Generates AEO-optimized content via Claude, manages schema markup, monitors AI citations, and publishes to WordPress — with human approval before anything goes live.

## Architecture

| Layer | Stack | Hosting (Azure, resource group `Axxiom-devs-foundry`) |
|---|---|---|
| Backend API + Workers | Python 3.12, FastAPI, APScheduler, SQLAlchemy | App Service `app-axxiom-aeo` on plan `asp-axxiom-mktg-hub` |
| Frontend Dashboard | React, TypeScript, Tailwind, TanStack Query | Served by the same App Service |
| Auth | Dashboard password (Key Vault) + signed session cookie | App Service |
| Database | PostgreSQL (`aeo` schema) | Azure Database for PostgreSQL `psql-axxiom-marketing`, database `axxiom_hub` |
| Secrets | App settings as Key Vault references | `kv-axxiom-marketing` |

Deploys, settings, migrations and the cutover history: [AZURE_DEPLOY.md](AZURE_DEPLOY.md).
Railway, Netlify and Supabase were retired in the 2026-09 move to Azure.

## Repository Structure

```
axxiomaeo/
├── backend/          # FastAPI + cron workers
├── frontend/         # React dashboard (built into the backend's App Service)
├── scripts/azure/    # package/deploy, settings sync, migrations, data scripts
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

# Requires PostgreSQL: a local Postgres via DATABASE_URL, or the Azure database with
# `az login` + AZURE_PG_USER (Entra token auth; the server firewall must allow you)
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
# Set VITE_AUTH_PROVIDER=password (and run the API with AUTH_PROVIDER=password)

npm run dev
```

Open http://localhost:5173

### Development Auth

Production sign-in is `AUTH_PROVIDER=password`: the dashboard password (`DASHBOARD_PASSWORD`) is checked by the API, which sets a signed HttpOnly session cookie (`DASHBOARD_SESSION_SECRET`). Local no-auth mode requires an explicit opt-in: `AUTH_DEV_BYPASS=true` with `ENVIRONMENT=development` and the legacy Supabase settings empty — a misconfigured deploy fails closed instead of open.

## Environment Variables

See [backend/.env.example](backend/.env.example) and [frontend/.env.example](frontend/.env.example).

Key backend variables:

- `ANTHROPIC_API_KEY` — Claude content generation
- `AZURE_PG_USER` / `AZURE_PG_CLIENT_ID` / `AZURE_PG_HOST` / `AZURE_PG_DATABASE` — Azure Postgres via managed identity (no password); `DATABASE_URL` for a local database
- `DB_SCHEMA` — `aeo` (default)
- `WP_APP_PASSWORD_*` / `WP_USERNAME_*` — WordPress Application Password + login per brand
- `WP_AUTHOR_ID_*` — WordPress user ID to set as the post author/byline per brand (optional; 0/unset = posts belong to the application-password account)
- `CITATION_PROVIDER` — `brightdata` (recommended — direct Bright Data AI-search APIs), `geo_aeo` (self-hosted tracker), `peec` (legacy), `none`, or `auto`
- `BRIGHT_DATA_API_KEY` — Bright Data API key (store as a secret) for `CITATION_PROVIDER=brightdata`; engines via `BRIGHT_DATA_PROVIDERS` (default `chatgpt,gemini,perplexity`)
- `GEO_AEO_TRACKER_URL` / `GEO_AEO_PROVIDERS` — only for the self-hosted [GEO/AEO Tracker](geo-aeo-tracker/README.md) path ([deployment runbook](geo-aeo-tracker/DEPLOYMENT.md))
- `PEEC_API_KEY` — Legacy Peec.ai citation monitoring (optional; use `CITATION_PROVIDER=peec`)
- `GOOGLE_SERVICE_ACCOUNT_JSON` — Base64-encoded service account for GSC + GA4
- `AUTH_PROVIDER`, `DASHBOARD_PASSWORD`, `DASHBOARD_SESSION_SECRET` — dashboard sign-in
- `SLACK_WEBHOOK_URL` — Worker notifications (optional)
- `DISCORD_WEBHOOK_URL` — Published-post notifications with live links (optional; Discord channel → Integrations → Webhooks)
- `AUTO_PUBLISH_ENABLED` — `true` (default) publishes validated drafts automatically; `false` restores the approval gate
- `FRONTEND_URL` — Deep links in Slack messages
- `CORS_ORIGINS` — only needed for a dashboard served from another origin (local dev); production serves the dashboard and API from one origin

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

Kill switch: set `AUTO_PUBLISH_ENABLED=false` in the Azure app settings to restore the approve-before-publish gate for the daily worker.

## Deploy (Azure)

See [AZURE_DEPLOY.md](AZURE_DEPLOY.md). In short: `./scripts/azure/package-app.sh --deploy`
builds the dashboard and ships backend + dashboard to `app-axxiom-aeo`; settings and secrets
come from `./scripts/azure/sync-app-settings.sh`; new `alter_aeo_vN.sql` files are applied by
hand with `scripts/azure/apply-migrations.sh` (the app never runs DDL on Azure).

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
