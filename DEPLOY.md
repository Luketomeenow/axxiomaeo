# Production deploy checklist

Complete in order. Detailed steps: [backend/RAILWAY_DEPLOY.md](backend/RAILWAY_DEPLOY.md), [frontend/NETLIFY_DEPLOY.md](frontend/NETLIFY_DEPLOY.md), [wordpress/README.md](wordpress/README.md).

- [ ] **Supabase:** Create the project and note the `DATABASE_URL` — no manual schema step needed. The backend auto-creates all tables from its ORM models and auto-applies every `backend/migrations/alter_aeo_v*.sql` file on startup (`run_alter_migrations()`); `migrations/aeo_schema.sql` is a legacy reference only, not part of the actual deploy path.
- [ ] **Railway backend:** Root `backend/`, env from [backend/.env.production.example](backend/.env.production.example), generate public domain
- [ ] **Netlify frontend:** Base `frontend/`, `VITE_API_URL` = Railway URL — see [frontend/NETLIFY_DEPLOY.md](frontend/NETLIFY_DEPLOY.md)
- [ ] **Supabase Auth:** Add Netlify URL to redirect allowlist
- [ ] **WordPress (×5):** App passwords + [wordpress/axxiom-aeo-schema.php](wordpress/axxiom-aeo-schema.php) (v1.1.1) on each site — [wordpress/ROLLOUT_VERIFICATION.md](wordpress/ROLLOUT_VERIFICATION.md)
- [ ] **Smoke test:** `python backend/scripts/smoke_test.py --base-url https://YOUR-RAILWAY-URL`, then `python backend/scripts/verify_rollout.py` for the fuller readiness check (DB, WordPress, citation provider, image pipeline)
- [ ] **Citations:** Set `CITATION_PROVIDER=none` until the tracker is live, or deploy it per [geo-aeo-tracker/DEPLOYMENT.md](geo-aeo-tracker/DEPLOYMENT.md) and set `GEO_AEO_TRACKER_URL`
- [ ] **Pilot publish:** Approve one draft → confirm JSON-LD in page source

## Smoke test (production)

```powershell
cd backend
$env:SMOKE_TEST_BASE_URL="https://your-app.up.railway.app"
$env:SMOKE_TEST_SKIP_SEED="1"
python scripts/smoke_test.py
```

Requires `SUPABASE_JWT_SECRET` in local `.env` (same as Railway) to mint a test JWT.
