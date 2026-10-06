# Azure deployment — Axxiom AEO platform

The AEO platform runs on the marketing hub's Azure footprint (same pattern as
`axxiom-insight-hub`): one Linux App Service serving the FastAPI API **and** the
built React dashboard, Microsoft Entra managed-identity auth to Azure Database
for PostgreSQL, secrets as Key Vault references. **Cut over on 2026-09-29**:
Railway, Netlify and Supabase are retired. The dashboard's Documentation page has an
**Azure Setup** tab with the operator's view of everything below.

| Piece | Azure resource |
|---|---|
| Subscription / RG | Axxiom AI Dev `fd7f41d1-e0df-4052-9e91-ff4cb2acf68f` / `Axxiom-devs-foundry` |
| Web app | `app-axxiom-aeo` — PYTHON 3.12, plan `asp-axxiom-mktg-hub` (westcentralus), Always-On, **1 instance** (in-process scheduler) — https://app-axxiom-aeo.azurewebsites.net |
| Identity | `umi-marketing-functions` (client `d66356a2-e306-45a9-abc1-947002ff321c`) — PG role + vault Secrets User |
| Database | `psql-axxiom-marketing` (PG 18, eastus2), database `axxiom_hub`, **schema `aeo`** — same DB as the hub because the hub reads/writes `aeo.*` |
| Secrets | `kv-axxiom-marketing`; name = env var lowercased with `_`→`-`; AEO-only ones prefixed `aeo-` |
| Auth | Shared dashboard password (`AUTH_PROVIDER=password`): vault `dashboard-password`, the same secret the hub uses; 12-hour HttpOnly `aeo_session` cookie signed with `aeo-dashboard-session-secret`; 8 wrong passwords in 15 min lock that client out for 15 min |
| AI | already Azure: Foundry Anthropic endpoint (`ANTHROPIC_BASE_URL`) + Azure OpenAI gpt-image-2 |

## How the app differs on Azure

- `AZURE_PG_USER` set → `DATABASE_URL`/`DB_PASSWORD` are ignored; the backend connects to
  `AZURE_PG_HOST`/`AZURE_PG_DATABASE` as that role with an Entra token as the password
  (`app/database.py::_entra_token`, refreshed per new connection, cached ~55 min). Managed
  identity in Azure, `az login` locally.
- `SCHEDULER_ENABLED=true` since the cutover (2026-09-29 15:00 UTC); `false` → API +
  dashboard only, no APScheduler jobs — the kill switch. Never run a second scheduler (a
  second instance or worker, or a laptop pointed at this database): every draft would
  publish twice.
- `FRONTEND_DIST_DIR` → FastAPI serves the Vite build (`frontend_dist/` in the zip) with an
  SPA fallback; API routes win. The dashboard is built with `VITE_API_URL=""` = same origin,
  so there is no CORS hop. Swagger and ReDoc move to `/api/docs` and `/api/redoc`, because
  the dashboard's Documentation page owns `/docs`.
- Startup command `bash startup.sh` → one uvicorn worker on `$PORT` (8000).

## Scripts (`scripts/azure/`)

| Script | What |
|---|---|
| `sync-app-settings.sh [--apply] [--no-secrets] [--live]` | Vault secrets (from `backend/.env`, only if missing) + app settings + startup command + health check path. `--live` sets `SCHEDULER_ENABLED=true`. Dry-run by default. **Always pass `--live` now**: without it the script writes `SCHEDULER_ENABLED=false` and every job stops. |
| `package-app.sh [--deploy]` | Builds the dashboard, stages `backend/` + `frontend_dist/`, zips, `az webapp deploy` (Oryx runs `pip install` server-side). |
| `aeo-data-cutover.sh [--init]` | **Azure Cloud Shell.** `--init` = first copy (schema + data, tables created under your login → owned by `dataservices`, mirrored to Fabric). Default = data-only wipe + reload + exact-count verification + identity-privilege check. |
| `apply-migrations.sh [ref]` | **Azure Cloud Shell, as dataservices.** Applies every idempotent `alter_aeo_v*.sql` from `ref` (default `main`) in version order, grants the app identity read/write on any new table, then checks RLS and the app's grants (both expect 0). `AZ_USER=` for anyone but Luke. |
| `drop-supabase-rls.sql` | **Azure Cloud Shell.** Drops the Supabase RLS policies and disables RLS on `aeo` tables. Idempotent. |
| `cloudshell-pg-client.sh [major]` | **Azure Cloud Shell.** Rootless modern `psql`/`pg_dump` into `~/pgclient` (no sudo there). |
| `aeo-value-check.sql` | **Azure Cloud Shell.** Read-only report: published articles, citations, AEO traffic, calls, cost. |

`az` on this Mac lives at `/opt/homebrew/bin/az`; npm at `~/.nvm/versions/node/v24.16.0/bin`.

## Runbook

### Status

**Cut over 2026-09-29 — Azure is the only runtime.** https://app-axxiom-aeo.azurewebsites.net
serves the dashboard + API on one origin with password sign-in; `/health` reports
`"database": "connected"` and `"data": "visible"`. Railway is stopped, the final data
copy verified, and the scheduler has been on since 15:00 UTC. The deployed build (14:00
UTC) includes the state fact sheet. Sections A and B stay below as the record of how it
was done. Still open: B5 (hub deploy), B6 (Foundry target, which first needs an
`AGENT_API_KEY`), B7 (Netlify redirect, branch `chore/retire-railway-netlify`), B8 (Zach:
AEOData notebook). Step A4 no longer applies; Supabase Auth is gone.

### A. Parallel run (no production impact)

0. **Cloud Shell needs a current pg client.** Its stock `pg_dump` is older than
   Supabase's server and refuses to dump ("server version mismatch"), and sudo
   is blocked there ("no new privileges"), so apt is not an option. Unpack the
   PGDG packages into `$HOME` instead — once per Cloud Shell session, since the
   containers are recycled:

   ```bash
   curl -sO https://raw.githubusercontent.com/Luketomeenow/axxiomaeo/main/scripts/azure/cloudshell-pg-client.sh
   bash cloudshell-pg-client.sh
   ```

   Cloud Shell runs Azure Linux, not Ubuntu, so the script falls back to
   micromamba + conda-forge there (a ~100 MB download into `~/pgclient`); on a
   Debian host it unpacks the PGDG `.deb` files instead. Either way
   `aeo-data-cutover.sh` finds the result on its own — it picks the newest
   `pg_dump` across `~/pgclient`, `/usr/lib/postgresql` and `/usr/bin`, and sets
   `LD_LIBRARY_PATH`. `PG_BIN=` overrides.
1. **Luke, Cloud Shell:** `export SUPABASE_DB_PASSWORD='…'` then
   `curl -sO https://raw.githubusercontent.com/Luketomeenow/axxiomaeo/main/scripts/azure/aeo-data-cutover.sh && bash aeo-data-cutover.sh --init`.
   Expect `0 mismatches / 16 tables` and `t|t` on the privilege line. If the privilege line
   shows `f`, run as your login: `GRANT USAGE ON SCHEMA aeo TO "umi-marketing-functions"; GRANT
   SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA aeo TO "umi-marketing-functions"; GRANT
   USAGE,SELECT ON ALL SEQUENCES IN SCHEMA aeo TO "umi-marketing-functions";`
1b. **Luke, Cloud Shell:** `psql … -f drop-supabase-rls.sql` (command in the file header).
   Expect `0 | 0` and `t`; then `/health` shows `"data": "visible"`.
2. **Secrets — Luke.** `./scripts/azure/sync-app-settings.sh --apply`. The
   non-secret half is already applied (`--no-secrets`); this adds the Key Vault
   secrets and their references. Prefer the live Railway values over the
   developer `.env`:
   ```bash
   railway variables --json | python3 -c 'import json,sys; [print(f"{k}={v}") for k,v in json.load(sys.stdin).items()]' > backend/.env.railway
   ENV_FILE=backend/.env.railway ./scripts/azure/sync-app-settings.sh --apply
   ```
   Until this runs the app has no Claude key, no Bright Data key, no WordPress
   passwords and no Discord/Slack webhooks — fine while the scheduler is off.
3. `./scripts/azure/package-app.sh --deploy`; watch `az webapp log tail -g Axxiom-devs-foundry -n app-axxiom-aeo`.
4. ~~Supabase → Authentication → URL Configuration: add the Azure URL to Redirect URLs.~~
   Obsolete: password sign-in replaced Supabase Auth on 2026-09-29.
5. Verify: `/health` → `"database": "connected"`; log in; Published Content, Citations,
   Reports show the same numbers as the Netlify site (both read the same snapshot — any
   difference is a hosting bug). Configuration blade: every vault ref shows a green check.

### B. Cutover (~30 min quiet window; nothing approved in the dashboard meanwhile)

Prerequisites from section A: RLS dropped (`/health` shows `"data": "visible"`), secrets
loaded, Azure login checked against Netlify.

1. **Stop Railway** so nothing writes to Supabase `aeo`: Railway dashboard → the backend
   service → **Settings → scale replicas to 0** (or `railway scale` / `railway down` from a
   linked checkout). Confirm `https://axxiomaeo-production.up.railway.app/health` stops answering.
2. **Cloud Shell:** `bash aeo-data-cutover.sh` (data mode) → `0 mismatches`, `t|t`, and
   "no table enforces RLS".
3. **Deploy the final build**, including any pending app changes (e.g. the state fact sheet
   branch), with the scheduler still off: `./scripts/azure/package-app.sh --deploy`; if it
   adds `alter_aeo_vN.sql` files, run `apply-migrations.sh <ref>` in Cloud Shell first.
4. **Scheduler on:** `./scripts/azure/sync-app-settings.sh --apply --live`. Watch the next
   job slot on System Health; publish one draft by hand → brand site + Discord.
5. **Marketing hub reads aeo from Azure:** merge hub branch `feat/aeo-schema-on-azure`,
   deploy the hub and `func-axxiom-mktg-node`, then set `AZURE_PG_SCHEMAS=aeo` on both:
   `az webapp config appsettings set -g Axxiom-devs-foundry -n app-axxiom-mktg-hub --settings AZURE_PG_SCHEMAS=aeo`
   (and the same for `func-axxiom-mktg-node`).
6. **Foundry agent:** Foundry portal → project Axxiom-Dev → Connected resources →
   `aeo-platform-api` → change the target from `https://axxiomaeo-production.up.railway.app`
   to `https://app-axxiom-aeo.azurewebsites.net`. Its custom key must equal the app's
   `AGENT_API_KEY` (vault `aeo-agent-api-key`). Railway never had that variable, so there
   is nothing to carry over: create the secret and the setting first (commands in the
   Azure Setup tab → Identity & secrets). Until then `/api/agent/*` answers 503.
7. **Netlify:** add to `netlify.toml` on main, above the SPA fallback:
   `[[redirects]] from = "/*"  to = "https://app-axxiom-aeo.azurewebsites.net/:splat"  status = 301  force = true`
   Pause builds after it deploys; delete the site after a quiet week.
8. **Zach:** retire the `AEOData` Fabric notebook (it reads Supabase `aeo`); the Postgres mirror
   carries the data now.

**Rollback** (any point after B.4): `SCHEDULER_ENABLED=false` on Azure, scale the Railway
service back to 1 replica (or `railway redeploy`), unset `AZURE_PG_SCHEMAS` on the hub. Rows written on Azure after the flip would need a reverse copy — decide inside the window.
This only works while the Railway service still exists. After that, roll back by
redeploying an older commit with `package-app.sh --deploy` (the B2 plan has no slots).
Migrations so far only add, so an older build runs on the current schema.

## Known gaps / follow-ups

- **Row-Level Security and migrations — decided by Zach, 2026-09-25.** The `aeo` tables
  carried Supabase's RLS policies across in the dump. On Supabase the app ran as the table
  owner so they never applied; on Azure it connects as `umi-marketing-functions`, a non-owner,
  so every table read as empty (while `/health` said connected). Zach declined adding the UMI
  to `dataservices` — the same identity runs the hub functions and would gain owner rights over
  all of `axxiom_hub`. Instead:
  1. **Drop the Supabase policies and disable RLS** on the `aeo` tables —
     `scripts/azure/drop-supabase-rls.sql`, run once in Cloud Shell as Luke. The policies were
     built for Supabase's anon/authenticated roles; grants do the protecting on Azure. Nothing
     in AEO depends on RLS (single app role, no `SET ROLE`, no `auth.uid()`; the FastAPI JWT
     check is the gatekeeper).
  2. **The app never runs DDL on Azure**: `DB_MIGRATIONS_ON_STARTUP=false` skips `create_all`
     and `alter_aeo_*.sql`. On each deploy that adds a migration, run
     `scripts/azure/apply-migrations.sh [ref]` in Cloud Shell as Luke/Trey (dataservices), which
     applies every idempotent `alter_aeo_v*.sql` in version order and checks RLS + grants.
  `/health` now reports `"data": "visible"` only when the app can actually read a brand row, so
  an RLS or grant problem shows up there instead of as empty pages.
- Cloud Shell runs Azure Linux with sudo blocked, and `$HOME` does not survive between
  sessions — re-fetch the scripts and re-run `cloudshell-pg-client.sh` each time.
- **Agent API is off.** `AGENT_API_KEY` is not set anywhere (app settings, vault, or the old
  Railway variables), so `/api/agent/*` answers 503 and the Foundry agents can't call in.
  Steps: Azure Setup tab → Identity & secrets.
- `sync-app-settings.sh` still defaults to the parallel-run `SCHEDULER_ENABLED=false`, so
  every run needs `--live` (or flip the default in the script).
- Alerts: resolved at cutover. The Discord webhooks are vault references
  (`aeo-discord-webhook-url`, `aeo-discord-schema-webhook-url`); `SLACK_WEBHOOK_URL` was
  empty on Railway too.
- No CI yet — deploys are the manual zip push, same as the hub. A GitHub Actions OIDC
  workflow is the natural next step for both repos.
- **Optimization agent (System Health).** Proposals work with no setup. Executing approved
  code changes needs: vault secret `aeo-optimizer-github-token` (fine-grained PAT on this repo:
  Actions read/write, Pull requests read) referenced by `OPTIMIZER_GITHUB_TOKEN`; repository
  secret `FOUNDRY_API_KEY` for `.github/workflows/aeo-optimizer.yml`; the repo setting "Allow
  GitHub Actions to create and approve pull requests"; and the workflow on `main` (GitHub only
  dispatches workflows on the default branch). Until `feat/azure-app-service` reaches `main`,
  set `OPTIMIZER_BASE_BRANCH=feat/azure-app-service`. Migration `alter_aeo_v16.sql` adds
  `aeo.optimization_proposals`. Steps: Azure Setup tab → Optimization agent. The Foundry key in
  GitHub is a stopgap: the target is OIDC federation to an Entra identity with Cognitive Services
  User on `axxiom-ai` (Zach), as in the builder-agent design.
- Supabase Auth is gone (password sign-in, 2026-09-29). Entra single sign-on remains an
  option; Zach would need to grant admin consent.
