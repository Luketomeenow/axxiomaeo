# Schema dedup audit — Yoast / Elementor (per site)

Run once per brand after MU plugin v1.1.0 is live and at least one AEO post is published.

**Goal:** Page source should show Axxiom schema from `aeo_schema_json` without conflicting duplicate JSON-LD for the same entities.

---

## Per-site audit

| Brand ID | Site | Test post URL | Axxiom JSON-LD present | Extra Yoast JSON-LD | Extra Elementor JSON-LD | Settings adjusted |
|----------|------|---------------|------------------------|---------------------|-------------------------|-------------------|
| `axxiom` | axxiomelevator.com | | [ ] | [ ] | [ ] | [ ] |
| `ameritex` | ameritexelevator.com | | [ ] | [ ] | [ ] | [ ] |
| `arizona_es` | azelevatorsolutions.com | | [ ] | [ ] | [ ] | [ ] |
| `liftech` | liftechelevator.com | | [ ] | [ ] | [ ] | [ ] |
| `motion` | motionelevator.com | | [ ] | [ ] | [ ] | [ ] |
| `quality` | qualityelevator.com | | [ ] | [ ] | [ ] | [ ] |
| `evolution` | evolutionelevator.com | | [ ] | [ ] | [ ] | [ ] |
| `ironhawk` | ironhawkelevator.com | | [ ] | [ ] | [ ] | [ ] |

---

## Steps (wp-admin + browser)

### 1. Publish or pick an AEO test post

Use Content Review **Approve & Publish** or an existing AEO post URL.

### 2. View page source

1. Open live post URL (front end, not wp-admin).
2. Ctrl+F → `application/ld+json`
3. Note how many `<script type="application/ld+json">` blocks appear and their `@type` values.

### 3. Yoast SEO

1. **SEO → Settings** (or **Search Appearance** on older Yoast).
2. Open **Schema** / **Site features → Schema**.
3. For **AEO blog posts**, prefer **only** schema from the MU plugin (`aeo_schema_json`).
4. Options (version-dependent):
   - Disable automatic Article/WebPage schema for posts if it duplicates Axxiom output, **or**
   - Use Yoast for non-AEO pages only and accept Yoast graph on posts only if types do not conflict.
5. Re-check page source after changes.

### 4. Elementor

1. **Elementor → Settings** — check for schema or integration features.
2. Disable any add-on that injects JSON-LD on single posts if it duplicates FAQ/Article schema.
3. Theme Builder templates do not block MU plugin `wp_head` output on singular posts.

### 5. Axxiom Schema Health

1. Dashboard → **Schema Health** → select brand.
2. Validate the test post URL — should pass when meta + MU plugin are correct.

---

## Acceptable vs problematic duplicates

| Situation | Action |
|-----------|--------|
| One Axxiom FAQPage/Article block only | Ideal |
| Yoast adds Organization/WebSite + Axxiom adds Article/FAQPage | Often OK if `@type` differ |
| Two Article or two FAQPage for same page | Adjust Yoast or Elementor — bad for SEO |
| JSON-LD missing entirely | Fix MU plugin v1.1.0 + meta — not a dedup issue |

---

## Related

- [ELEMENTOR.md — Avoid duplicate JSON-LD](ELEMENTOR.md#avoid-duplicate-json-ld-yoast--elementor)
- [PILOT_PUBLISH.md](PILOT_PUBLISH.md)
