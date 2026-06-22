# MU plugin redeploy — v1.1.0 (all 8 sites)

Re-upload [`axxiom-aeo-schema.php`](axxiom-aeo-schema.php) after pulling this repo change.  
**Why:** v1.1.0 adds `register_post_meta` so REST API saves `aeo_schema_json` (required for publish + JSON-LD).

**SFTP steps:** [WP_ENGINE_SETUP.md — Part 1](WP_ENGINE_SETUP.md#part-1--upload-the-mu-plugin-sftp)

---

## Per-site checklist

| Brand ID | Site | MU plugin v1.1.0 | Must-Use visible | Pilot / test publish |
|----------|------|------------------|------------------|----------------------|
| `axxiom` | axxiomelevator.com | [ ] | [ ] | [ ] |
| `ameritex` | ameritexelevator.com | [ ] | [ ] | [ ] ← **pilot first** |
| `arizona_es` | azelevatorsolutions.com | [ ] | [ ] | [ ] |
| `liftech` | liftechelevator.com | [ ] | [ ] | [ ] |
| `motion` | motionelevator.com | [ ] | [ ] | [ ] |
| `quality` | qualityelevator.com | [ ] | [ ] | [ ] |
| `evolution` | evolutionelevator.com | [ ] | [ ] | [ ] |
| `ironhawk` | ironhawkelevator.com | [ ] | [ ] | [ ] |

---

## Upload steps (each site)

1. WP Engine portal → select environment → **Users & SFTP**
2. SFTP to port **2222** → `wp-content/mu-plugins/`
3. Upload / overwrite **`axxiom-aeo-schema.php`** from `axxiomaeo/wordpress/`
4. wp-admin → **Plugins → Must-Use** → confirm **Axxiom AEO Schema** version **1.1.0**

No cache flush or plugin activation required.

---

## After AmeriTex pilot

Complete [PILOT_PUBLISH.md](PILOT_PUBLISH.md), then roll out remaining 7 sites and spot-check Schema Health per brand.
