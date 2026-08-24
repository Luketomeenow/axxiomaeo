# WordPress setup (all 6 brand sites)

Required for **Approve & Publish** and **Schema Review** to show JSON-LD on live pages,
and (v1.2.0+) for AEO indexing plumbing: robots.txt with sitemap, generated `/llms.txt`,
and the IndexNow key file that lets the backend push every publish into Bing's index
(which is what ChatGPT search reads).

**WP Engine (step-by-step):** see [WP_ENGINE_SETUP.md](WP_ENGINE_SETUP.md)  
**Elementor Pro (Theme Builder + Post Content):** see [ELEMENTOR.md](ELEMENTOR.md)  
**v1.1.1 redeploy (all 5 sites):** [REDEPLOY_CHECKLIST.md](REDEPLOY_CHECKLIST.md)

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
| quality | `WP_APP_PASSWORD_QUALITY` |

Optional per brand: `WP_AUTHOR_ID_{brand_id}` — the WordPress user ID to credit as post author/byline (find it in **Users → all users**, click a name, `user_id=N` in the URL). Unset = posts belong to the Application Password account.

## 2. The mu-plugin (must-have)

Copy [`axxiom-aeo-schema.php`](axxiom-aeo-schema.php) (**v1.2.0** — JSON-LD output +
robots.txt + `/llms.txt` + IndexNow key file) to:

```
wp-content/mu-plugins/axxiom-aeo-schema.php
```

Create `mu-plugins` folder if it does not exist. Must-use plugins load automatically.

**v1.2.0 upgrade note:** also **delete any physical `robots.txt` or `llms.txt` files**
at the web root (WP Engine serves physical files before WordPress runs, which hides
the generated versions — several sites currently serve an *empty* physical robots.txt).

## 3. Verify (per site, ~1 min)

1. Approve one draft in **Content Review** → open the live post URL → **View Page
   Source** → `application/ld+json` appears in `<head>`.
2. `https://<site>/robots.txt` → shows `Allow: /`, an `LLM-Policy:` line, and a
   `Sitemap:` line (not blank).
3. `https://<site>/llms.txt` → returns the generated site summary + article list.
4. `https://<site>/c550d35adee3985871ee6e39bd7f8e35.txt` → returns exactly that key.

## 4. IndexNow back-catalog (once, after all 6 sites verify)

New posts ping IndexNow automatically at publish. To push the existing back-catalog
into Bing's pipeline once:

```
cd backend && venv/bin/python scripts/indexnow_submit_all.py          # dry-run
cd backend && venv/bin/python scripts/indexnow_submit_all.py --apply
```

The script skips any site whose key file isn't live yet, so it's safe to run early.

Also recommended (manual, once): verify each site in **Bing Webmaster Tools**
(you can import all sites from Google Search Console in two clicks) — gives
crawl/index visibility on the Bing side.
