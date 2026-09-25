# Azure deployment — Axxiom AEO platform

The AEO platform runs on the marketing hub's Azure footprint (same pattern as
`axxiom-insight-hub`): one Linux App Service serving the FastAPI API **and** the
built React dashboard, Microsoft Entra managed-identity auth to Azure Database
for PostgreSQL, secrets as Key Vault references. Railway + Netlify + Supabase
stay live until the cutover below.

| Piece | Azure resource |
|---|---|
| Subscription / RG | Axxiom AI Dev `fd7f41d1-e0df-4052-9e91-ff4cb2acf68f` / `Axxiom-devs-foundry` |
| Web app | `app-axxiom-aeo` — PYTHON 3.12, plan `asp-axxiom-mktg-hub` (westcentralus), Always-On, **1 instance** (in-process scheduler) — https://app-axxiom-aeo.azurewebsites.net |
| Identity | `umi-marketing-functions` (client `d66356a2-e306-45a9-abc1-947002ff321c`) — PG role + vault Secrets User |
| Database | `psql-axxiom-marketing` (PG 18, eastus2), database `axxiom_hub`, **schema `aeo`** — same DB as the hub because the hub reads/writes `aeo.*` |
| Secrets | `kv-axxiom-marketing`; name = env var lowercased with `_`→`-`; AEO-only ones prefixed `aeo-` |
| Auth | Supabase Auth (unchanged) — the dashboard still logs in against project `cdlssoeqqfrgckpxewhn`; the API verifies its JWTs via JWKS |
| AI | already Azure: Foundry Anthropic endpoint (`ANTHROPIC_BASE_URL`) + Azure OpenAI gpt-image-2 |

## How the app differs on Azure

- `AZURE_PG_USER` set → `DATABASE_URL`/`DB_PASSWORD` are ignored; the backend connects to
  `AZURE_PG_HOST`/`AZURE_PG_DATABASE` as that role with an Entra token as the password
  (`app/database.py::_entra_token`, refreshed per new connection, cached ~55 min). Managed
  identity in Azure, `az login` locally.
- `SCHEDULER_ENABLED=false` → API + dashboard only, no APScheduler jobs. **This is the
  parallel-run state.** Flip to `true` only after Railway is stopped — two schedulers would
  publish every draft twice.
- `FRONTEND_DIST_DIR` → FastAPI serves the Vite build (`frontend_dist/` in the zip) with an
  SPA fallback; API routes win. The dashboard is built with `VITE_API_URL=""` = same origin,
  so there is no CORS hop.
- Startup command `bash startup.sh` → one uvicorn worker on `$PORT` (8000).

## Scripts (`scripts/azure/`)

| Script | What |
|---|---|
| `sync-app-settings.sh [--apply] [--live]` | Vault secrets (from `backend/.env`, only if missing) + app settings + startup command + health check path. `--live` sets `SCHEDULER_ENABLED=true`. Dry-run by default. |
| `package-app.sh [--deploy]` | Builds the dashboard, stages `backend/` + `frontend_dist/`, zips, `az webapp deploy` (Oryx runs `pip install` server-side). |
| `aeo-data-cutover.sh [--init]` | **Azure Cloud Shell.** `--init` = first copy (schema + data, tables created under your login → owned by `dataservices`, mirrored to Fabric). Default = data-only wipe + reload + exact-count verification + identity-privilege check. |

`az` on this Mac lives at `/opt/homebrew/bin/az`; npm at `~/.nvm/versions/node/v24.16.0/bin`.

## Runbook

### Status

**Parallel run is LIVE (2026-09-21).** https://app-axxiom-aeo.azurewebsites.net —
dashboard + API on one origin, `/health` reports `database: connected` through the
managed identity. `SCHEDULER_ENABLED=false`, so Railway is still the only writer and
nothing publishes twice. Data copied with `0 mismatches / 16 tables`. Steps 0–1 and 3
below are done; what remains is the RLS drop (step 1b), the secret load (step 2), the
Supabase redirect (step 4), and section B.

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
4. Supabase → Authentication → URL Configuration: add `https://app-axxiom-aeo.azurewebsites.net` to Redirect URLs.
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
   `AGENT_API_KEY` (vault `aeo-agent-api-key`, loaded from Railway in step A2).
7. **Netlify:** add to `netlify.toml` on main, above the SPA fallback:
   `[[redirects]] from = "/*"  to = "https://app-axxiom-aeo.azurewebsites.net/:splat"  status = 301  force = true`
   Pause builds after it deploys; delete the site after a quiet week.
8. **Zach:** retire the `AEOData` Fabric notebook (it reads Supabase `aeo`); the Postgres mirror
   carries the data now.

**Rollback** (any point after B.4): `SCHEDULER_ENABLED=false` on Azure, scale the Railway
service back to 1 replica (or `railway redeploy`), unset `AZURE_PG_SCHEMAS` on the hub. Rows written on Azure after the flip would need a reverse copy — decide inside the window.

## Known gaps / follow-ups

- Alerts: `DISCORD_WEBHOOK_URL`, `DISCORD_SCHEMA_WEBHOOK_URL`, `SLACK_WEBHOOK_URL` live only in
  Railway variables, not in `backend/.env` — sourcing `ENV_FILE` from `railway variables`
  (step 2) covers them; otherwise the Azure app posts no notifications.
- Cloud Shell runs Azure Linux with sudo blocked, and `$HOME` does not survive between
  sessions — re-fetch the scripts and re-run `cloudshell-pg-client.sh` each time.
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

- Alerts: `DISCORD_WEBHOOK_URL`, `DISCORD_SCHEMA_WEBHOOK_URL`, `SLACK_WEBHOOK_URL` live only in
  Railway variables, not in `backend/.env` — sourcing `ENV_FILE` from `railway variables`
  (step 2) covers them; otherwise the Azure app posts no notifications.
- Cloud Shell runs Azure Linux with sudo blocked, and `$HOME` does not survive between
  sessions — re-fetch the scripts and re-run `cloudshell-pg-client.sh` each time.
- **RLS blocks the app from the data (blocking, found 2026-09-21).** Supabase
  enables Row-Level Security on the tables it exposes through PostgREST, and
  `pg_dump` carried that across. On Supabase the app connected as the table
  owner, so RLS never applied; on Azure it connects as `umi-marketing-functions`,
  a non-owner, so RLS is enforced against it. The symptom is silent: `SELECT`
  returns zero rows and `INSERT` is refused, while `/health` still reports the
  database connected. It showed up as the startup seed trying to re-insert the
  `axxiom` brand that demonstrably exists in the copy. `has_table_privilege`
  reports `true` throughout, so the cutover script now checks RLS separately.

  **Fix — one grant, from Zach:**
  ```sql
  GRANT dataservices TO "umi-marketing-functions";
  ```
  Membership in the owning role restores exactly the posture the app had on
  Supabase (it ran as the owner), leaves every policy in place and enforced for
  everyone else, and fixes the migration problem below at the same time. Nothing
  in this codebase uses RLS for access control: no session roles, no `auth.uid()`,
  and the FastAPI JWT check is the only gatekeeper. The alternative — disabling
  RLS on the `aeo` tables — weakens a control that costs nothing to keep, so
  prefer the grant.

- **Migration ownership (blocking before cutover).** `alter_aeo_vN.sql` runs
  `ALTER TABLE aeo.*`, which requires ownership. The restore created the tables as
  Luke, so they belong to `dataservices`, and the app's identity is not a member.
  Each migration file is now attempted independently and a failure is logged rather
  than taking startup down, but new migrations will not apply until Zach runs
  `GRANT dataservices TO "umi-marketing-functions"` (or they are applied by hand in
  Cloud Shell).
- No CI yet — deploys are the manual zip push, same as the hub. A GitHub Actions OIDC
  workflow is the natural next step for both repos.
- Entra ID login (replacing Supabase Auth) is the last Supabase dependency to remove.
