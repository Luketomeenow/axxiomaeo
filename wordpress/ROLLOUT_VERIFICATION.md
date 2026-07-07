# Rollout verification (Phase 0)

Run after deploying MU plugin, Application Passwords, and GEO tracker.

## Automated check

```bash
cd backend
python scripts/verify_rollout.py
```

## Per-brand checklist (all 5)

- [ ] MU plugin `axxiom-aeo-schema.php` v1.1.1+ in `wp-content/mu-plugins/`
- [ ] Application Password `Axxiom AEO` + `WP_APP_PASSWORD_{BRAND}` in backend env
- [ ] (Optional) `WP_AUTHOR_ID_{BRAND}` set for the post author/byline
- [ ] Elementor Single Post template includes **Post Content** widget ([ELEMENTOR.md](ELEMENTOR.md))
- [ ] Yoast schema dedup audit ([SCHEMA_DEDUP_CHECKLIST.md](SCHEMA_DEDUP_CHECKLIST.md))
- [ ] Test publish → view source → `application/ld+json` present
- [ ] GA4 property ID + GSC site URL in Brand Settings

## GEO tracker

Full step-by-step runbook (Bright Data setup, Railway/Vercel deploy, smoke test, cost controls, troubleshooting): [geo-aeo-tracker/DEPLOYMENT.md](../geo-aeo-tracker/DEPLOYMENT.md). Quick summary:

1. Deploy the tracker (Railway recommended) and set Bright Data API keys on it
2. Backend env:
   ```env
   CITATION_PROVIDER=geo_aeo
   GEO_AEO_TRACKER_URL=https://your-tracker.example.com
   GEO_AEO_PROVIDERS=perplexity,chatgpt,google_ai
   ```
3. Run **Citations → Run validation** in dashboard or wait for 1st/15th cron

## Authority (off-platform)

See [AUTHORITY_CHECKLIST.md](AUTHORITY_CHECKLIST.md) for GBP, NAP, and review consistency.
