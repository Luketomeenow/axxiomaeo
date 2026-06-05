# Production deploy checklist

Complete in order. Detailed steps: [backend/RAILWAY_DEPLOY.md](backend/RAILWAY_DEPLOY.md), [frontend/NETLIFY_DEPLOY.md](frontend/NETLIFY_DEPLOY.md), [wordpress/README.md](wordpress/README.md).

- [ ] **Supabase:** Run [backend/migrations/aeo_schema.sql](backend/migrations/aeo_schema.sql) in SQL Editor
- [ ] **Railway backend:** Root `backend/`, env from [backend/.env.production.example](backend/.env.production.example), generate public domain
- [ ] **Netlify frontend:** Base `frontend/`, `VITE_API_URL` = Railway URL — see [frontend/NETLIFY_DEPLOY.md](frontend/NETLIFY_DEPLOY.md)
- [ ] **Supabase Auth:** Add Netlify URL to redirect allowlist
- [ ] **WordPress (×8):** App passwords + [wordpress/axxiom-aeo-schema.php](wordpress/axxiom-aeo-schema.php) on each site
- [ ] **Smoke test:** `python backend/scripts/smoke_test.py --base-url https://YOUR-RAILWAY-URL`
- [ ] **Citations:** Set `CITATION_PROVIDER=none` until tracker is live, or deploy [geo-aeo-tracker-app](geo-aeo-tracker-app) and set `GEO_AEO_TRACKER_URL`
- [ ] **Pilot publish:** Approve one draft → confirm JSON-LD in page source

## Smoke test (production)

```powershell
cd backend
$env:SMOKE_TEST_BASE_URL="https://your-app.up.railway.app"
$env:SMOKE_TEST_SKIP_SEED="1"
python scripts/smoke_test.py
```

Requires `SUPABASE_JWT_SECRET` in local `.env` (same as Railway) to mint a test JWT.
