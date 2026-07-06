# WP Engine setup — Axxiom AEO Schema plugin

Step-by-step guide for all **5 brand WordPress sites** hosted on **WP Engine**.  
Required so **Approve & Publish** and **Schema Review** output JSON-LD on live pages.

**Plugin file in this repo:** [`axxiom-aeo-schema.php`](axxiom-aeo-schema.php) (v1.1.1+)  
**Install path on server:** `wp-content/mu-plugins/axxiom-aeo-schema.php`  
**Elementor Pro sites:** see [ELEMENTOR.md](ELEMENTOR.md) (Theme Builder + Post Content widget)

---

## What you are installing

The Axxiom dashboard publishes posts/pages via the WordPress REST API and saves structured data in post meta field **`aeo_schema_json`**.

**v1.1.1** does three things:

1. **Registers** `aeo_schema_json` for REST API writes (`show_in_rest`) on **posts** and **pages** — without this, WordPress may silently ignore schema sent by the backend.
2. **Outputs** that meta in the page `<head>` as JSON-LD.
3. **Escapes** `</` inside the stored JSON so a `</script>` sequence in schema text can't break out of the script block (added in v1.1.1).

This must-use (MU) plugin reads that meta and outputs:

```html
<script type="application/ld+json">…</script>
```

in the page `<head>` so search engines, AI crawlers, and **Schema Health** can see your schema.

**This is not installed from the WordPress plugin store.** You upload the PHP file via SFTP or WP Engine’s file tools.

---

## Prerequisites

- WP Engine login with access to each brand environment
- SFTP client (FileZilla, WinSCP, or Cyberduck) **or** WP Engine SFTP / SSH gateway
- The plugin file from this repo on your computer
- WordPress admin access on each site (for Application Passwords)

### All 5 sites (repeat steps per site)

| Brand ID | Typical site | Backend env var (app password) |
|----------|--------------|--------------------------------|
| `axxiom` | axxiomelevatorfl.com | `WP_APP_PASSWORD_AXXIOM` |
| `ameritex` | ameritexelevator.com | `WP_APP_PASSWORD_AMERITEX` |
| `arizona_es` | azelevatorsolutions.com | `WP_APP_PASSWORD_ARIZONA_ES` |
| `liftech` | liftechelevator.com | `WP_APP_PASSWORD_LIFTECH` |
| `quality` | qualityelevator.com | `WP_APP_PASSWORD_QUALITY` |

Also set `WP_USERNAME_{BRAND_ID}` in backend env (e.g. `WP_USERNAME_AMERITEX=your-wp-username`). Optionally set `WP_AUTHOR_ID_{BRAND_ID}` to a WordPress user ID to credit as the post author/byline instead of the Application Password account (find the ID in **Users → all users**, click a name, `user_id=N` in the URL).

---

## Part 1 — Upload the MU plugin (SFTP)

Do this **once per brand site**.

### Step 1: Open WP Engine portal

1. Go to [https://my.wpengine.com](https://my.wpengine.com) and sign in.
2. Select the **environment** for the brand (e.g. AmeriTex Elevator production).

### Step 2: Get SFTP credentials

1. In the environment, open **Users & SFTP** (or **SFTP**).
2. Note:
   - **SFTP address** (host)
   - **Username**
   - **Password** (or create/reset SFTP password)
   - **Port** — WP Engine typically uses **2222** (not 21 or 22)

### Step 3: Connect with an SFTP client

1. Open FileZilla (or WinSCP).
2. **Host:** SFTP address from WP Engine  
3. **Port:** `2222`  
4. **Protocol:** SFTP  
5. **User / Password:** from step 2  
6. Connect.

### Step 4: Find `wp-content`

WP Engine paths look like:

```
/sites/{environment-name}/
```

Under that you should see:

```
wp-admin/
wp-content/
wp-includes/
```

Open **`wp-content`**.

### Step 5: Create `mu-plugins` (if missing)

1. If there is **no** `mu-plugins` folder, create it:
   - Name must be exactly: **`mu-plugins`** (lowercase, hyphen).
2. Do **not** put the file in `wp-content/plugins/` — that is for normal plugins.

### Step 6: Upload the plugin file

1. On your computer, locate:
   ```
   axxiomaeo/wordpress/axxiom-aeo-schema.php
   ```
2. Upload it to:
   ```
   wp-content/mu-plugins/axxiom-aeo-schema.php
   ```
3. Confirm:
   - Filename is **`axxiom-aeo-schema.php`** (not `.php.txt`)
   - File is directly inside `mu-plugins`, not in a subfolder

### Step 7: Confirm in WordPress admin

1. Log into that site’s **wp-admin**.
2. Go to **Plugins → Must-Use** (label may vary; some installs show this only when MU plugins exist).
3. You should see:
   - **Axxiom AEO Schema**
   - Version **1.1.1** (or newer)
   - Description mentions REST registration and JSON-LD output

No “Activate” button is required — MU plugins load automatically.

**Upgrading from an older version:** Re-upload the file from this repo (overwrite on server). No wp-admin steps required. See [REDEPLOY_CHECKLIST.md](REDEPLOY_CHECKLIST.md).

### Optional: Mu Manager

You may install **Mu Manager** from the plugin store to list or toggle MU plugins in the UI. You still must **upload the PHP file via SFTP first** — Mu Manager does not ship our plugin.

---

## Part 2 — WordPress Application Password (API access)

The Axxiom backend publishes content using the WordPress REST API. Each site needs an **Application Password**.

Do this **once per brand site**.

### Step 1: Open your user profile

1. Log into wp-admin for that brand.
2. Go to **Users → Profile** (your own admin account).

### Step 2: Create Application Password

1. Scroll to **Application Passwords**.
2. **New Application Password Name:** `Axxiom AEO`
3. Click **Add New Application Password**.
4. Copy the generated password immediately (spaces are OK — backend strips them).

### Step 3: Save in backend environment

In Railway / `backend/.env` (local) set:

```env
WP_APP_PASSWORD_AMERITEX=xxxx xxxx xxxx xxxx xxxx xxxx
WP_USERNAME_AMERITEX=your-wordpress-username
WP_AUTHOR_ID_AMERITEX=9
```

Repeat for each brand using the table above. `WP_AUTHOR_ID_*` is optional — omit or set to `0` to leave posts owned by the Application Password account.

**Security:** Never commit real passwords to git. Use Railway secrets or local `.env` only.

---

## Part 3 — Verify end-to-end

### A. Confirm MU plugin on a published post

1. In the Axxiom dashboard, **Content Review** → approve a test draft (or use an existing published post that has schema meta).
2. Open the **live post URL** in a browser.
3. **View Page Source** (Ctrl+U).
4. Search for: `application/ld+json`
5. You should see JSON-LD in the `<head>`.

If publish succeeds in the dashboard but JSON-LD is **missing** in source → MU plugin is not installed or not on a singular post/page.

### B. Confirm Schema Health (dashboard)

1. Open **Schema Health** in the Axxiom app.
2. Run validation for that brand (after a publish).
3. Pages with meta + MU plugin should report valid JSON-LD.

### C. Common mistakes

| Problem | Fix |
|---------|-----|
| File in `plugins/` instead of `mu-plugins/` | Move to `wp-content/mu-plugins/` |
| Wrong folder name (`mu_plugins`, `muplugins`) | Rename to `mu-plugins` |
| File named `.php.txt` | Rename to `.php` only |
| Only installed on one site | Repeat for all 5 environments |
| REST publish works, no JSON-LD in source | MU plugin missing — not an API issue |
| Publish OK but `aeo_schema_json` meta empty | Upgrade to plugin **v1.1.1+** (`register_post_meta`) |
| Post title shows but body empty on front end | Elementor Single Post template missing **Post Content** widget — [ELEMENTOR.md](ELEMENTOR.md) |
| Duplicate JSON-LD in page source | Yoast/Elementor schema overlap — [schema dedup checklist](SCHEMA_DEDUP_CHECKLIST.md) |

---

## Part 4 — Elementor Pro (Theme Builder)

All brand sites use **Elementor Pro** with a **Single Post** template that includes the **Post Content** widget.

| Check | Why |
|-------|-----|
| Single Post template uses **Post Content** (or **Theme Post Content**) | API HTML in `post_content` only renders inside this widget |
| Template assigned to **All Posts** (or correct categories) | AEO posts use the right shell |
| Do **not** “Edit with Elementor” on API-published posts to rebuild body | Builder save can replace `post_content` / add `_elementor_data` |
| Use Elementor for chrome only (header, footer, CTAs) | Body stays classic/API HTML from Axxiom |

Full guide: [ELEMENTOR.md](ELEMENTOR.md)

**Pilot first on AmeriTex:** [PILOT_PUBLISH.md](PILOT_PUBLISH.md)

---

## Part 5 — Repeat for all 5 brands

Use [REDEPLOY_CHECKLIST.md](REDEPLOY_CHECKLIST.md) or this summary per site:

- [ ] SFTP upload: `wp-content/mu-plugins/axxiom-aeo-schema.php` (**v1.1.1+**)
- [ ] wp-admin: **Axxiom AEO Schema** visible under Must-Use plugins
- [ ] Elementor Single Post template has **Post Content** widget
- [ ] Application Password created: `Axxiom AEO`
- [ ] `WP_APP_PASSWORD_{BRAND}` + `WP_USERNAME_{BRAND}` set in backend env
- [ ] Test publish → `aeo_schema_json` in post meta + `application/ld+json` in page source
- [ ] Yoast/Elementor schema audited — [SCHEMA_DEDUP_CHECKLIST.md](SCHEMA_DEDUP_CHECKLIST.md)

---

## Staging vs production

WP Engine often has **staging** and **production** environments.

- Install the MU plugin on **production** before go-live.
- For testing, install on **staging** first, point backend at staging URL temporarily, or publish a test draft only on staging.

Each environment has its own SFTP path and may need its own Application Password.

---

## Alternative (not recommended)

If SFTP is blocked, paste the `add_action('wp_head', …)` block from [`axxiom-aeo-schema.php`](axxiom-aeo-schema.php) into the active theme’s **`functions.php`** (**Appearance → Theme File Editor**).

Downside: schema output breaks if you change themes. MU plugin is the supported approach.

---

## Related docs

- [README.md](README.md) — short overview
- [ELEMENTOR.md](ELEMENTOR.md) — Theme Builder, Post Content, Yoast conflicts
- [REDEPLOY_CHECKLIST.md](REDEPLOY_CHECKLIST.md) — v1.1.1 rollout on all 5 sites
- [PILOT_PUBLISH.md](PILOT_PUBLISH.md) — AmeriTex first publish verification
- [SCHEMA_DEDUP_CHECKLIST.md](SCHEMA_DEDUP_CHECKLIST.md) — Yoast/Elementor JSON-LD audit
- [DEPLOY.md](../DEPLOY.md) — full production checklist
- [backend/.env.example](../backend/.env.example) — all `WP_APP_PASSWORD_*` variables
