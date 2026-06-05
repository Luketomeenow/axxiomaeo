# Netlify deployment — Axxiom AEO dashboard

## 1. Connect repo

1. [app.netlify.com](https://app.netlify.com) → **Add new site** → **Import from Git**
2. Repository: `Luketomeenow/axxiomaeo`
3. **Base directory:** `frontend`
4. **Build command:** `npm run build` (from [netlify.toml](netlify.toml))
5. **Publish directory:** `frontend/dist`

## 2. Environment variables

| Variable | Value |
|----------|--------|
| `VITE_API_URL` | Railway backend URL, e.g. `https://your-app.up.railway.app` |
| `VITE_SUPABASE_URL` | `https://cdlssoeqqfrgckpxewhn.supabase.co` |
| `VITE_SUPABASE_ANON_KEY` | Supabase → Project Settings → API → anon public |

Redeploy after changing env vars (Vite bakes them at build time).

## 3. Supabase Auth allowlist

Supabase Dashboard → **Authentication** → **URL Configuration**:

- **Site URL:** your Netlify URL (e.g. `https://axxiom-aeo.netlify.app`)
- **Redirect URLs:** add the same Netlify URL and `http://localhost:5173`

## 4. Update Railway CORS

On Railway backend, set:

```
CORS_ORIGINS=https://YOUR-NETLIFY-URL.netlify.app,http://localhost:5173
FRONTEND_URL=https://YOUR-NETLIFY-URL.netlify.app
```

Redeploy backend after updating CORS.

## 5. Verify

1. Open Netlify URL → log in with Supabase user
2. Dashboard loads KPIs (may be zero until content/citations run)
3. **Brand Settings** → save a GA4 ID → confirms API connectivity
