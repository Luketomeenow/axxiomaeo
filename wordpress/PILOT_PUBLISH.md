# Pilot publish — AmeriTex (Elementor + AEO)

Use this checklist for the **first end-to-end publish** on AmeriTex before rolling out to all 5 brands.

**Site:** ameritexelevator.com  
**Brand ID:** `ameritex`  
**Backend env:** `WP_APP_PASSWORD_AMERITEX`, `WP_USERNAME_AMERITEX`, `WP_AUTHOR_ID_AMERITEX` (optional — post author/byline)

---

## Before you start

- [ ] [`axxiom-aeo-schema.php`](axxiom-aeo-schema.php) **v1.1.1+** uploaded to `wp-content/mu-plugins/` on AmeriTex WP Engine environment
- [ ] **Plugins → Must-Use** shows **Axxiom AEO Schema**
- [ ] Application Password `Axxiom AEO` created; credentials in `backend/.env`
- [ ] Elementor **Single Post** template includes **Post Content** widget ([ELEMENTOR.md](ELEMENTOR.md))
- [ ] Backend running locally or on Railway; you can log into Axxiom dashboard

---

## Publish from dashboard

1. Open **Content Review**.
2. Pick a ready draft (`faq_hub` or `local_page` recommended).
3. Preview HTML + validation + schema JSON-LD.
4. Click **Approve & Publish**.
5. Note the returned post URL (or find it in WordPress **Posts**).

---

## Verify on the live site

### A. Body content (Elementor)

1. Open the **live post URL** in a browser (not wp-admin preview).
2. Confirm article HTML is visible (headings, paragraphs, tables).
3. If body is **empty** but title shows → Single Post template is missing **Post Content** widget.

### B. JSON-LD in page source

1. **View Page Source** (Ctrl+U).
2. Search: `application/ld+json`
3. Confirm JSON-LD from Axxiom (FAQPage / Article) is present in `<head>`.
4. If publish succeeded but **no** JSON-LD → MU plugin missing or `aeo_schema_json` meta empty (re-upload v1.1.1 plugin).

### C. Meta in WordPress

1. wp-admin → **Posts** → open the published post.
2. Check **Custom Fields** for `aeo_schema_json` (may need “Custom Fields” panel enabled in Screen Options).

### D. Schema Health (Axxiom app)

1. **Schema Health** → select AmeriTex → run validation.
2. URL should report valid JSON-LD after meta + MU plugin are correct.

### E. Schema dedup

1. In page source, count distinct `application/ld+json` blocks.
2. If Yoast adds extra schema, follow [ELEMENTOR.md — Avoid duplicate JSON-LD](ELEMENTOR.md#avoid-duplicate-json-ld-yoast--elementor).

---

## Success criteria

| Check | Pass? |
|-------|-------|
| Post visible on front end with full HTML body | |
| `aeo_schema_json` in post meta | |
| `application/ld+json` in page source | |
| Schema Health valid for post URL | |
| No unintended duplicate conflicting schema | |

---

## Roll out to other 4 brands

Repeat [WP_ENGINE_SETUP.md](WP_ENGINE_SETUP.md) SFTP + Application Password for each brand, then one test publish each (or spot-check Schema Health).
