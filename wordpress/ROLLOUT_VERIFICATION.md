# Rollout verification (Phase 0)

Run after deploying MU plugin, Application Passwords, and GEO tracker.

## Automated check

```bash
cd backend
python scripts/verify_rollout.py
```

## Per-brand checklist (all 8)

- [ ] MU plugin `axxiom-aeo-schema.php` v1.1.0+ in `wp-content/mu-plugins/`
- [ ] Application Password `Axxiom AEO` + `WP_APP_PASSWORD_{BRAND}` in backend env
- [ ] Elementor Single Post template includes **Post Content** widget ([ELEMENTOR.md](ELEMENTOR.md))
- [ ] Yoast schema dedup audit ([SCHEMA_DEDUP_CHECKLIST.md](SCHEMA_DEDUP_CHECKLIST.md))
- [ ] Test publish → view source → `application/ld+json` present
- [ ] GA4 property ID + GSC site URL in Brand Settings

## GEO tracker

1. Clone [geo-aeo-tracker](https://github.com/danishashko/geo-aeo-tracker) and deploy (Railway/Vercel)
2. Set Bright Data API keys on tracker
3. Backend env:
   ```env
   CITATION_PROVIDER=geo_aeo
   GEO_AEO_TRACKER_URL=https://your-tracker.example.com
   GEO_AEO_PROVIDERS=perplexity,google_ai
   ```
4. Run **Citations → Run validation** in dashboard or wait for 1st/15th cron

## Authority (off-platform)

See [AUTHORITY_CHECKLIST.md](AUTHORITY_CHECKLIST.md) for GBP, NAP, and review consistency.
