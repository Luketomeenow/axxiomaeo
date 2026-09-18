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

### A. Parallel run (no production impact)

1. **Luke, Cloud Shell:** `export SUPABASE_DB_PASSWORD='…'` then
   `curl -sO https://raw.githubusercontent.com/Luketomeenow/axxiomaeo/main/scripts/azure/aeo-data-cutover.sh && bash aeo-data-cutover.sh --init`.
   Expect `0 mismatches / 16 tables` and `t|t` on the privilege line. If the privilege line
   shows `f`, run as your login: `GRANT USAGE ON SCHEMA aeo TO "umi-marketing-functions"; GRANT
   SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA aeo TO "umi-marketing-functions"; GRANT
   USAGE,SELECT ON ALL SEQUENCES IN SCHEMA aeo TO "umi-marketing-functions";`
2. `./scripts/azure/sync-app-settings.sh --apply` (SCHEDULER_ENABLED=false).
3. `./scripts/azure/package-app.sh --deploy`; watch `az webapp log tail -g Axxiom-devs-foundry -n app-axxiom-aeo`.
4. Supabase → Authentication → URL Configuration: add `https://app-axxiom-aeo.azurewebsites.net` to Redirect URLs.
5. Verify: `/health` → `"database": "connected"`; log in; Published Content, Citations,
   Reports show the same numbers as the Netlify site (both read the same snapshot — any
   difference is a hosting bug). Configuration blade: every vault ref shows a green check.

### B. Cutover (~20 min quiet window; nothing approved in the UI meanwhile)

1. **Stop Railway** (service → Settings → remove/replicas 0, or pause). Nothing writes to Supabase `aeo` now.
2. **Cloud Shell:** `bash aeo-data-cutover.sh` (data mode) → `0 mismatches`.
3. `./scripts/azure/sync-app-settings.sh --apply --live` → scheduler on; app restarts.
4. Verify the next scheduled slot fires (`job_runs` / System Health page), publish one draft
   by hand → appears on the brand site + Discord.
5. Repoint consumers: Foundry `aeo-platform-api` connection base URL → Azure host; Netlify
   site → `_redirects` `/* https://app-axxiom-aeo.azurewebsites.net/:splat 301`, then pause builds.
6. Hub: switch its `aeo` readers (`src/server/aeo/queue.ts`, `brandReport.ts`, `aeo.adapter.ts`)
   from Supabase `.schema("aeo")` to the Azure PG client — otherwise the hub's AEO tab reads
   a frozen Supabase copy. Zach retires the `AEOData` Fabric notebook (it also reads Supabase).

**Rollback** (any point after B.3): `SCHEDULER_ENABLED=false` on Azure, restart the Railway
service. Rows written on Azure after the flip would need a reverse copy — decide inside the window.

## Known gaps / follow-ups

- Alerts: `DISCORD_WEBHOOK_URL`, `DISCORD_SCHEMA_WEBHOOK_URL`, `SLACK_WEBHOOK_URL` live only in
  Railway variables, not in `backend/.env` — export them into `backend/.env` (or set
  `ENV_FILE`) before `sync-app-settings.sh --apply`, or the Azure app posts no notifications.
- Startup migrations (`ALTER TABLE aeo.* …`) need table ownership. Tables restored by Luke are
  owned by `dataservices`; if the app identity is not a member of that role, new
  `alter_aeo_vN.sql` files fail silently on Azure (init errors are caught) → ask Zach for
  `GRANT dataservices TO "umi-marketing-functions"`, or run new migrations by hand in Cloud Shell.
- No CI yet — deploys are the manual zip push, same as the hub. A GitHub Actions OIDC
  workflow is the natural next step for both repos.
- Entra ID login (replacing Supabase Auth) is the last Supabase dependency to remove.
