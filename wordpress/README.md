# WordPress setup (all 8 brand sites)

Required for **Approve & Publish** and **Schema Review** to show JSON-LD on live pages.

**WP Engine (step-by-step):** see [WP_ENGINE_SETUP.md](WP_ENGINE_SETUP.md)  
**Elementor Pro (Theme Builder + Post Content):** see [ELEMENTOR.md](ELEMENTOR.md)  
**v1.1.0 redeploy (all 8 sites):** [REDEPLOY_CHECKLIST.md](REDEPLOY_CHECKLIST.md)

## 1. Application Password

On each WordPress site:

1. **Users → Profile → Application Passwords**
2. Create password named `Axxiom AEO`
3. Store in Railway/backend env as `WP_APP_PASSWORD_{brand_id}` (see [backend/.env.example](../backend/.env.example))

| Brand ID | Env var |
|----------|---------|
| axxiom | `WP_APP_PASSWORD_AXXIOM` |
| ameritex | `WP_APP_PASSWORD_AMERITEX` |
| arizona_es | `WP_APP_PASSWORD_ARIZONA_ES` |
| liftech | `WP_APP_PASSWORD_LIFTECH` |
| motion | `WP_APP_PASSWORD_MOTION` |
| quality | `WP_APP_PASSWORD_QUALITY` |
| evolution | `WP_APP_PASSWORD_EVOLUTION` |
| ironhawk | `WP_APP_PASSWORD_IRONHAWK` |

## 2. Schema output (must-have)

Copy [`axxiom-aeo-schema.php`](axxiom-aeo-schema.php) (**v1.1.0+** — registers meta for REST + outputs JSON-LD) to:

```
wp-content/mu-plugins/axxiom-aeo-schema.php
```

Create `mu-plugins` folder if it does not exist. Must-use plugins load automatically.

**Alternative:** paste the `add_action('wp_head', ...)` block from that file into each theme's `functions.php`.

## 3. Verify publish

1. Approve one draft in **Content Review**
2. Open the live post URL → **View Page Source**
3. Search for `application/ld+json` — schema should appear in `<head>`

Without step 2, the API publish succeeds but Schema Health will always report missing JSON-LD.
