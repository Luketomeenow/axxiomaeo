# Production deploy

Production runs on Azure. Follow [AZURE_DEPLOY.md](AZURE_DEPLOY.md) — resources, deploy
commands, settings sync, hand-applied migrations, and the Railway/Netlify/Supabase cutover.

- **Deploy:** `./scripts/azure/package-app.sh --deploy`
- **Settings / secrets:** `./scripts/azure/sync-app-settings.sh --apply` (Key Vault references)
- **Migrations:** `bash scripts/azure/apply-migrations.sh <ref>` in Azure Cloud Shell
- **WordPress (×6):** App passwords + [wordpress/axxiom-aeo-schema.php](wordpress/axxiom-aeo-schema.php) — [wordpress/ROLLOUT_VERIFICATION.md](wordpress/ROLLOUT_VERIFICATION.md)
- **Smoke test:** `python backend/scripts/smoke_test.py --base-url https://app-axxiom-aeo.azurewebsites.net`
