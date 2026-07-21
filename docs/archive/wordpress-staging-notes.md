# Archived: DigitalOcean WordPress staging (`.wpress` import)

This document was moved from `docs/wordpress-staging-notes.md` on 2026-03-21. It describes the **abandoned** Docker/DigitalOcean staging host (`naba-wp-staging.herencia.build`) and All-in-One WP Migration attempts. **Current staging** is Hostinger — see `docs/WORDPRESS_STAGING_SETUP.md` and `docs/plan-wp-frontend-integration.md`.

---

## NaBA WordPress Staging – Backup Import Notes

This doc summarizes what we tried to get the production `.wpress` backup imported into the Docker-based staging instance at `https://naba-wp-staging.herencia.build`, and outlines possible paths forward.

---

## Context

- **Production site:** `https://natural-building-alliance.org`
- **Staging site:** `https://naba-wp-staging.herencia.build`
- **Staging host:** DigitalOcean VPS (`142.93.177.21`) with:
  - `nginx` reverse proxy
  - `docker-compose` running:
    - `wordpress` container (named `wordpress_staging`)
    - `mysql` container
- **Migration tool:** All-in-One WP Migration plugin exporting a **~1.48GB `.wpress`** file from production.
- **Goal:** Restore that backup into the staging WordPress so staging is a full copy of production (for safe plugin/core tests and future headless/astro integration).

At the end of this attempt, **infrastructure is healthy** (nginx, Docker, PHP, MySQL) but the **big backup is still not fully restored** into staging.

---

## What we tried (chronological)

### 1. Base staging environment

- Brought up Docker-based staging on the DO VPS using `docker-compose` (see `WORDPRESS_STAGING_SETUP.md` for full details).
- Configured `nginx` vhost for `naba-wp-staging.herencia.build` with SSL via Certbot.
- Verified that a fresh WordPress install was reachable at `https://naba-wp-staging.herencia.build`.

### 2. Browser import via All-in-One WP Migration (initial attempts)

**Symptoms:**
- Import from **All-in-One WP Migration → Import → File** failed quickly with:
  > Your file exceeds the upload limit set by your host web server.

**Mitigations applied:**

- In the **WordPress container**:
  - Created `/usr/local/etc/php/conf.d/uploads.ini` with:
    - `upload_max_filesize = 2G`
    - `post_max_size = 2G`
    - `memory_limit = 512M` (later raised to `1024M`)
    - `max_execution_time = 0`
    - `max_input_time = 3600`
  - Restarted the `wordpress_staging` container so the new PHP limits were applied.
  - Verified via `php -i` that `upload_max_filesize` and `post_max_size` were `2G`.

- In **nginx**:
  - Updated the HTTPS server block in `/etc/nginx/sites-enabled/wordpress-staging` to:
    - `client_max_body_size 2G;`
    - `proxy_read_timeout 3600` → later `14400`
    - `proxy_connect_timeout 3600` → later `14400`
    - `proxy_send_timeout 3600` → later `14400`
  - Reloaded nginx after config tests.

**Result:**  
- The error about exceeding upload limit went away, and the browser-based import progressed much further (tens of percent) but eventually timed out or failed near the end of the process.

### 3. Tweaks for mid-import timeouts

To handle the large backup and long-running import:

- **PHP:**
  - Set `max_execution_time = 0` and `max_input_time = 3600` in `uploads.ini`.
  - Restarted the `wordpress_staging` container to pick up changes.

- **nginx:**
  - Increased proxy timeouts (up to 4 hours) for `proxy_read_timeout`, `proxy_connect_timeout`, and `proxy_send_timeout` in the HTTPS `location /` block.

Despite these changes, browser imports still failed partway or near the end of the process (after significant progress).

### 4. WP-CLI restore attempt (no browser)

To avoid browser and nginx upload issues entirely:

1. Copied the `.wpress` file to the server under `/opt/wordpress-staging/`.
2. Copied it into the container:
   - `docker exec wordpress_staging mkdir -p /var/www/html/wp-content/ai1wm-backups`
   - `docker cp <backup>.wpress wordpress_staging:/var/www/html/wp-content/ai1wm-backups/`
   - `docker exec wordpress_staging chown -R www-data:www-data /var/www/html/wp-content/ai1wm-backups`
3. Installed **WP-CLI** inside the container and made `wp` available in `$PATH`.
4. Attempted to run:
   - `wp ai1wm restore <backup>.wpress --allow-root`

**Result:**

- The command aborted with:
  > This feature is available in Unlimited Extension.  
  > You can purchase it from this address: https://servmask.com/products/unlimited-extension

Conclusion: **CLI restore (and some large restore behaviors) require the paid Unlimited Extension**, which we do not currently have.

### 5. Current staging behavior

- `https://naba-wp-staging.herencia.build` is running WordPress (Twenty Twenty-Five default).
- The full production backup (`.wpress`) is present on the server and inside the container under `wp-content/ai1wm-backups/`.
- Browser-based restore has repeatedly failed due to size/time complexity, and CLI restore is gated behind the paid extension.

---

## Current status

- **Infra:** Docker + nginx + SSL + PHP + MySQL are configured and healthy.
- **Backup file:** Successfully uploaded to the server and copied into the container’s `ai1wm-backups` directory.
- **Staging content:** Still **not** a full clone of production; it’s effectively a fresh WordPress install.
- **Known constraints:**
  - All-in-One WP Migration free edition is very limited for **large** (~1.5GB) restores.
  - CLI restore via `wp ai1wm restore` requires the **Unlimited Extension**.
  - Browser-based restore is fragile even with high nginx/PHP limits, due to the size and duration of the operation.

---

## Options going forward

### Option A – Purchase the Unlimited Extension (most straightforward for current setup)

**Pros:**
- Unlocks CLI restore (`wp ai1wm restore`) and removes many restore/import restrictions.
- Works well with the existing Docker + WP-CLI setup.
- Allows using the already-uploaded `.wpress` file in `ai1wm-backups`.

**Cons:**
- Paid license; need to purchase from ServMask.

**Rough steps (once purchased & installed on staging):**

1. Activate the Unlimited Extension on **staging**.
2. Ensure backup file is in `wp-content/ai1wm-backups/`.
3. Run:  
   `docker exec -it wordpress_staging bash -c 'cd /var/www/html && wp ai1wm restore <backup>.wpress --allow-root'`

This is the path of least resistance given all the prep work already done.

### Option B – Use production host’s cPanel / managed staging instead

If the **production host** (for `natural-building-alliance.org`) offers:

- **cPanel / Softaculous staging**, or  
- A managed WordPress **“Staging”** feature,

then:

- Use that host-provided staging to clone production to a staging URL (e.g., `staging.natural-building-alliance.org`).
- Use that environment for plugin/core/theme tests and content changes.
- Keep the DO-based Docker staging either:
  - As a separate sandbox for experiments, or
  - Decommission it if it’s no longer needed.

This offloads backup/restore complexity to the hosting provider’s tooling.

### Option C – Different migration approach (no All-in-One `.wpress`)

Instead of relying on All-in-One WP Migration, you can:

1. **Database:**
   - Create a SQL dump from production (via `mysqldump` or host’s DB tools).
   - Import that SQL into the staging MySQL database.
2. **Files:**
   - Copy `wp-content/uploads` and any custom themes/plugins via `rsync` or SFTP to staging.
3. Update `wp-config.php` and run a **search/replace** on URLs (production → staging) using WP-CLI or another tool.

**Pros:**
- No `.wpress` size limit or plugin-specific constraints.

**Cons:**
- More manual and error-prone; requires DB and file-level access to the production host.

### Option D – Use a different migration plugin/tool

Try another migration plugin or tool that:

- Handles large sites better in the free tier, or
- Supports server-side imports/CLI without a paid add-on.

Examples (to be evaluated before use):

- Plugins that can **pull** from a remote site or database.
- Tools that use direct DB + file sync instead of a monolithic `.wpress` file.

This would require installing the alternative plugin on both production and staging and following its migration process.

### Option E – Narrower staging scope (partial clone)

If the main goal is **testing specific features** (e.g., MemberPress flows, directory data, or a subset of content), consider:

- Creating a **smaller export** from production (e.g., database with limited tables, or limited uploads).
- Or even building a **minimal synthetic dataset** on staging (e.g., a few representative members and pages).

This avoids having to move the full 1.5GB site until there’s a clear need.

---

## Suggested next steps (short list)

1. **Decide on strategy:**
   - Either purchase the **Unlimited Extension** (Option A) and complete the restore in the current Docker setup, **or**
   - Investigate whether the production host provides **cPanel/managed staging** and, if so, adopt that instead (Option B).
2. If going with **Option A**:
   - Purchase and activate the extension on staging.
   - Run the CLI restore against the backup already in `ai1wm-backups`.
3. If going with **Option B**:
   - Log into the production host’s account.
   - Look for **Staging** / **Softaculous → WordPress → Create Staging**.
   - Use that environment for production-like testing; keep this DO staging as optional infra.
4. Only if needed, explore **Options C–E** for manual or partial migrations.
