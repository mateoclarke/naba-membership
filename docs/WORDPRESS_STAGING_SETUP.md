# NABA WordPress Staging Setup

Documentation for the WordPress staging environment for Natural Building Alliance (NABA).

## Server Details

- **Production Site:** https://natural-building-alliance.org
- **Staging Site:** https://naba-wp-staging.herencia.build
- **VPS Provider:** DigitalOcean (shared with Listmonk & Umami)
- **IP Address:** 142.93.177.21
- **Location on VPS:** `/opt/wordpress-staging/`

## SSH Access

```bash
ssh root@142.93.177.21
```

## Requirements

- **Minimum RAM:** 2GB (upgraded from 1GB — MySQL 8.0 requires significant memory)
- **Disk Space:** ~2-3GB for WordPress + database + uploads

## Easier alternatives (if available)

If you can use one of these, staging is much simpler than the Docker + migration path below (no large uploads, no nginx/PHP limit tweaks).

| Option                             | What it does                                                                                                                                                                                                                 | When to use it                                                                                                                                                                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **cPanel staging**                 | Many cPanel hosts offer **one-click staging**: clone the live site to a subdomain (e.g. `staging.natural-building-alliance.org`) or subdirectory. The copy runs on the server, so there’s no browser upload of a 1.5GB file. | Use if production is on a host that provides cPanel (or similar) and a “Staging” or “Softaculous” staging feature. In cPanel, look for **WordPress**, **Softaculous**, or **Staging** and follow the host’s “Create staging” flow. |
| **Host-built-in staging**          | Managed WordPress hosts (e.g. WP Engine, Kinsta, Flywheel) often have a **Staging** button in their dashboard that clones the site with one click.                                                                           | Use if production is on such a host.                                                                                                                                                                                               |
| **WP Staging (or similar) plugin** | A plugin that clones the live site into a subfolder or subdomain on the **same server** (e.g. `natural-building-alliance.org/staging`). No export/import; it copies files and DB on the server.                              | Use if you have no cPanel but do have enough disk space and a host that allows this (some shared hosts restrict it).                                                                                                               |

If you get **cPanel access** for the production host: use the host’s staging tool first. You’ll get a staging URL, can test there, and only need the Docker/VPS setup below if you want staging on your own server (e.g. herencia.build) instead of the host’s.

---

## Initial Setup (Already Completed)

### Step 1: Add DNS Record

In your DNS provider for `herencia.build`:

| Type | Name            | Value         |
| ---- | --------------- | ------------- |
| A    | naba-wp-staging | 142.93.177.21 |

### Step 2: Create Directory Structure

```bash
ssh root@142.93.177.21
mkdir -p /opt/wordpress-staging
cd /opt/wordpress-staging
```

### Step 3: Create Docker Compose File

```bash
nano docker-compose.yml
```

```yaml
services:
  wordpress:
    image: wordpress:latest
    container_name: naba_staging
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:80"
    environment:
      WORDPRESS_DB_HOST: db
      WORDPRESS_DB_USER: wordpress
      WORDPRESS_DB_PASSWORD: YOUR_DB_PASSWORD_HERE
      WORDPRESS_DB_NAME: naba_staging
      WORDPRESS_CONFIG_EXTRA: |
        define('WP_HOME', 'https://naba-wp-staging.herencia.build');
        define('WP_SITEURL', 'https://naba-wp-staging.herencia.build');
        define('WP_ENVIRONMENT_TYPE', 'staging');
        define('WP_MEMORY_LIMIT', '256M');
        define('WP_MAX_MEMORY_LIMIT', '512M');
    volumes:
      - wordpress_data:/var/www/html
    depends_on:
      - db
    networks:
      - naba

  db:
    image: mysql:8.0
    container_name: naba_staging_db
    restart: unless-stopped
    environment:
      MYSQL_DATABASE: naba_staging
      MYSQL_USER: wordpress
      MYSQL_PASSWORD: YOUR_DB_PASSWORD_HERE
      MYSQL_ROOT_PASSWORD: YOUR_ROOT_PASSWORD_HERE
    volumes:
      - db_data:/var/lib/mysql
    networks:
      - naba

volumes:
  wordpress_data:
  db_data:

networks:
  naba:
```

**IMPORTANT:** The `WORDPRESS_DB_PASSWORD` and `MYSQL_PASSWORD` must match exactly!

### Step 4: Generate Secure Passwords

```bash
openssl rand -base64 24  # For DB_PASSWORD
openssl rand -base64 24  # For ROOT_PASSWORD
```

### Step 5: Start Containers

```bash
cd /opt/wordpress-staging
docker compose up -d
```

### Step 6: Configure Nginx

```bash
nano /etc/nginx/sites-available/naba-staging
```

```nginx
server {
    listen 80;
    server_name naba-wp-staging.herencia.build;

    client_max_body_size 2G;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 600;
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
    }
}
```

Enable and get SSL:

```bash
ln -s /etc/nginx/sites-available/naba-staging /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
certbot --nginx -d naba-wp-staging.herencia.build
```

### Step 7: Increase PHP Upload Limits

For importing large `.wpress` files (1.48GB+):

```bash
docker exec naba_staging bash -c 'echo "upload_max_filesize = 2G
post_max_size = 2G
memory_limit = 512M
max_execution_time = 600
max_input_time = 600" > /usr/local/etc/php/conf.d/uploads.ini'

docker compose restart wordpress
```

## Common Commands

### Check Status

```bash
cd /opt/wordpress-staging && docker compose ps
```

### View Logs

```bash
# WordPress logs
docker compose logs -f wordpress

# MySQL logs
docker compose logs -f db
```

### Restart Services

```bash
cd /opt/wordpress-staging
docker compose restart wordpress
docker compose restart db
```

### Stop Everything

```bash
cd /opt/wordpress-staging
docker compose down
```

### Start Everything

```bash
cd /opt/wordpress-staging
docker compose up -d
```

### Enter WordPress Container

```bash
docker exec -it naba_staging bash
```

### Enter MySQL Container

```bash
docker exec -it naba_staging_db mysql -u wordpress -p naba_staging
```

### Check Memory Usage

```bash
free -h
```

## Importing Production Data

### Method 1: Import via WP-CLI (recommended for large backups)

No browser upload — you copy the backup onto the server and restore from the command line. Avoids upload limits and timeouts.

**Important:** The **CLI restore** (`wp ai1wm restore`) is only available in the **paid [Unlimited Extension](https://servmask.com/products/unlimited-extension)**. The free plugin shows: _"This feature is available in Unlimited Extension."_ If you don’t have the extension, use **Method 2** (browser import with the limits fixed) or try **restore from Backups in wp-admin** (step below).

**Prerequisites:** You have the `.wpress` file (from production: **All-in-One WP Migration → Export → Export To File**). You have SSH access to the staging server (`root@142.93.177.21`). Replace `wordpress_staging` with your container name if different (see `docker ps`). The official `wordpress` Docker image does **not** include WP-CLI — install it once (step 4a) before using `wp` commands.

| Step   | Where        | What to do                                                                                                                                                                                                                                                                            |
| ------ | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **1**  | Your laptop  | Export the backup from production (wp-admin → All-in-One WP Migration → Export To File) and note the path to the downloaded `.wpress` file.                                                                                                                                           |
| **2**  | Your laptop  | Copy the backup to the server (use your actual file path and filename): `scp /path/to/your-backup.wpress root@142.93.177.21:/opt/wordpress-staging/`                                                                                                                                  |
| **3**  | Server (SSH) | SSH in: `ssh root@142.93.177.21` then `cd /opt/wordpress-staging`                                                                                                                                                                                                                     |
| **4a** | Server       | **Install WP-CLI in the container** (required once; the wordpress image doesn’t include it): `docker exec wordpress_staging bash -c 'curl -sO https://raw.githubusercontent.com/wp-cli/builds/gh-pages/phar/wp-cli.phar && chmod +x wp-cli.phar && mv wp-cli.phar /usr/local/bin/wp'` |
| **4b** | Server       | Ensure the All-in-One WP Migration plugin is installed: `docker exec wordpress_staging bash -c 'cd /var/www/html && wp plugin install all-in-one-wp-migration --activate --allow-root'`                                                                                               |
| **5**  | Server       | Create the backup directory and copy the file into the container (use your actual filename): `docker exec wordpress_staging mkdir -p /var/www/html/wp-content/ai1wm-backups` then `docker cp your-backup.wpress wordpress_staging:/var/www/html/wp-content/ai1wm-backups/`            |
| **6**  | Server       | Fix ownership: `docker exec wordpress_staging chown -R www-data:www-data /var/www/html/wp-content/ai1wm-backups`                                                                                                                                                                      |
| **7**  | Server       | List backups (optional): `docker exec wordpress_staging bash -c 'cd /var/www/html && wp ai1wm list-backups --allow-root'` — note the exact filename.                                                                                                                                  |
| **8**  | Server       | Run the restore (use the filename from the list): `docker exec -it wordpress_staging bash -c 'cd /var/www/html && wp ai1wm restore your-backup.wpress --allow-root'` Confirm when prompted. Wait for it to finish.                                                                    |
| **9**  | Browser      | Log in at https://naba-wp-staging.herencia.build/wp-admin/ with your **production** WordPress credentials. Go to **Settings → Permalinks** and click **Save**.                                                                                                                        |

**If you see “This feature is available in Unlimited Extension”:** CLI restore requires the [paid extension](https://servmask.com/products/unlimited-extension). Alternatives: (1) In wp-admin go to **All-in-One WP Migration → Backups** — if your backup appears there (file is already in `ai1wm-backups`), try **Restore** (large restores may still need the extension). (2) Use **Method 2** (browser import) with nginx/PHP limits and timeouts raised as in the doc. (3) Purchase the Unlimited Extension to use `wp ai1wm restore` and other premium features.

**One-liner reference (after the file is in the container and ownership is fixed; requires Unlimited Extension):**

```bash
docker exec -it wordpress_staging bash -c 'cd /var/www/html && wp ai1wm restore YOUR-FILENAME.wpress --allow-root'
```

---

### Method 2: All-in-One WP Migration (browser upload)

**Container name:** Run `docker ps` and note the WordPress container name (e.g. `wordpress_staging` or `naba_staging`). Use that name in place of `naba_staging` in the commands below if they differ.

1. **Export from production:** (already done — 1.48GB .wpress file)
   - Login to https://natural-building-alliance.org/wp-admin/
   - All-in-One WP Migration → Export → Export To File
   - Download the `.wpress` file

2. **Remove upload size limit on staging:** (run from `/opt/wordpress-staging`; replace `naba_staging` with your container name if needed)

   Official guide: [ServMask — How to Increase Maximum Upload File Size](https://help.servmask.com/2018/10/27/how-to-increase-maximum-upload-file-size-in-wordpress/) (plugin, hosting, or manual).

   **Option A — wp-config.php (recommended by ServMask, works reliably in Docker):** Add PHP limits in WordPress so they apply to every request. Run once (replace `naba_staging` with your container name):

   ```bash
   docker exec naba_staging bash -c 'if ! grep -q "upload_max_filesize" /var/www/html/wp-config.php; then
     ( head -1 /var/www/html/wp-config.php
       echo "// Raise limits for All-in-One WP Migration import (see help.servmask.com)"
       echo "@ini_set( \"upload_max_filesize\", \"2G\" );"
       echo "@ini_set( \"post_max_size\", \"2G\" );"
       echo "@ini_set( \"memory_limit\", \"512M\" );"
       echo "@ini_set( \"max_execution_time\", \"600\" );"
       echo "@ini_set( \"max_input_time\", \"600\" );"
       tail -n +2 /var/www/html/wp-config.php
     ) > /tmp/wp-config.new && mv /tmp/wp-config.new /var/www/html/wp-config.php
   fi'
   ```

   **Option B — PHP conf.d + unlimited extension:** (if Option A is not enough, do both)
   - Increase PHP limits in the container (see **Step 7** above).
   - Create the unlimited extension plugin:

   ```bash
   docker exec naba_staging bash -c 'cd /var/www/html/wp-content/plugins && \
     mkdir -p all-in-one-wp-migration-unlimited-extension && \
     echo "<?php
   /*
   Plugin Name: All-in-One WP Migration Unlimited Extension
   Description: Removes the upload limit
   */
   add_filter('\''ai1wm_max_file_size'\'', function() { return 536870912 * 20; });" \
     > all-in-one-wp-migration-unlimited-extension/all-in-one-wp-migration-unlimited-extension.php'
   ```

   Then in wp-admin: **Plugins → Installed Plugins → Activate** "All-in-One WP Migration Unlimited Extension".

3. **Import to staging:**
   - Login to https://naba-wp-staging.herencia.build/wp-admin/
   - Install "All-in-One WP Migration" plugin
   - Activate the unlimited extension (Plugins → Installed Plugins)
   - All-in-One WP Migration → Import
   - Upload the `.wpress` file (may take 10-20 minutes)
   - After import, login with **production credentials**

## Post-Import Configuration

### Disable Search Engine Indexing

In WordPress admin: Settings → Reading → Check "Discourage search engines from indexing this site"

### Disable Outgoing Emails

To prevent staging from emailing real members:

```bash
docker exec -it naba_staging bash
cd /var/www/html
wp plugin install disable-emails --activate --allow-root
exit
```

### Password Protect Staging (Recommended)

```bash
apt install apache2-utils -y
htpasswd -c /etc/nginx/.htpasswd-naba staging_user
```

Edit nginx config:

```bash
nano /etc/nginx/sites-available/naba-staging
```

Add inside `location /` block:

```nginx
        auth_basic "NABA Staging - Restricted";
        auth_basic_user_file /etc/nginx/.htpasswd-naba;
```

```bash
nginx -t
systemctl reload nginx
```

## Backup

### Backup Database

```bash
cd /opt/wordpress-staging
docker exec naba_staging_db mysqldump -u wordpress -p'YOUR_PASSWORD' naba_staging > backup_$(date +%Y%m%d).sql
```

### Backup WordPress Files

```bash
docker cp naba_staging:/var/www/html /opt/wordpress-staging/backup_files_$(date +%Y%m%d)
```

## Troubleshooting

### "Import failed" — file exceeds upload limit

If All-in-One WP Migration shows "Your file exceeds the upload limit set by your host", follow [ServMask’s official guide](https://help.servmask.com/2018/10/27/how-to-increase-maximum-upload-file-size-in-wordpress/) (plugin, hosting, or manual). For this Docker setup:

**Why wp-config.php often isn’t enough:** Many PHP builds do not allow changing `upload_max_filesize` or `post_max_size` with `ini_set()` (they are PHP_INI_SYSTEM). You must set them in **php.ini** (or a file in `conf.d/`) and restart the container.

**Full fix (copy-paste from `/opt/wordpress-staging`; replace `wordpress_staging` if your container has a different name):**

```bash
cd /opt/wordpress-staging
CONTAINER=wordpress_staging

# 1) PHP limits in conf.d (takes effect after restart)
docker exec $CONTAINER bash -c 'echo "upload_max_filesize = 2G
post_max_size = 2G
memory_limit = 512M
max_execution_time = 600
max_input_time = 600" > /usr/local/etc/php/conf.d/uploads.ini'

docker compose restart wordpress
# Wait ~15 seconds for the container to come back, then:

# 2) Unlimited extension for All-in-One WP Migration
docker exec $CONTAINER bash -c 'mkdir -p /var/www/html/wp-content/plugins/all-in-one-wp-migration-unlimited-extension && cat > /var/www/html/wp-content/plugins/all-in-one-wp-migration-unlimited-extension/all-in-one-wp-migration-unlimited-extension.php << "EOF"
<?php
/*
Plugin Name: All-in-One WP Migration Unlimited Extension
Description: Removes the upload limit
*/
add_filter("ai1wm_max_file_size", function() { return 536870912 * 20; });
EOF'
```

Then in wp-admin: **Plugins → Activate** "All-in-One WP Migration Unlimited Extension". Ensure nginx has `client_max_body_size 2G;` for this site (Step 6). Retry the import.

1. **Use the correct container name.** Run `docker ps` and use the WordPress container name (e.g. `wordpress_staging`) in all commands below.
2. **Apply limits via wp-config.php (optional).** Can help with `memory_limit` and timeouts; often does _not_ change upload limits. See **Importing Production Data → Step 2 → Option A**.
3. **Apply PHP conf.d limits and restart (required for large uploads).** Replace `CONTAINER` with your WordPress container name (e.g. `wordpress_staging`):
   ```bash
   docker exec CONTAINER bash -c 'echo "upload_max_filesize = 2G
   post_max_size = 2G
   memory_limit = 512M
   max_execution_time = 600
   max_input_time = 600" > /usr/local/etc/php/conf.d/uploads.ini'
   docker compose restart wordpress
   ```
   Then create the unlimited extension (same `CONTAINER`):
   ```bash
   docker exec CONTAINER bash -c 'cd /var/www/html/wp-content/plugins && \
     mkdir -p all-in-one-wp-migration-unlimited-extension && \
     echo "<?php
   /*
   Plugin Name: All-in-One WP Migration Unlimited Extension
   Description: Removes the upload limit
   */
   add_filter('\''ai1wm_max_file_size'\'', function() { return 536870912 * 20; });" \
     > all-in-one-wp-migration-unlimited-extension/all-in-one-wp-migration-unlimited-extension.php'
   ```
4. **In wp-admin:** Plugins → Installed Plugins → ensure **"All-in-One WP Migration Unlimited Extension"** is **Activated** (if you use Option B).
5. **Confirm nginx allows large bodies:** The staging site is proxied by nginx. Ensure the server block has `client_max_body_size 2G;` (see **Step 6**). Then run `nginx -t && systemctl reload nginx` on the host.
6. **Retry import** (refresh the Import page and upload again).

**Verify PHP limits (optional):** After step 3 and restart, confirm the container sees the new limits:

```bash
docker exec CONTAINER php -i | grep -E "upload_max_filesize|post_max_size"
```

You should see `upload_max_filesize => 2G` and `post_max_size => 2G`. If you still see low values (e.g. 2M), the conf.d file may not be in a path PHP loads — check with `docker exec CONTAINER ls -la /usr/local/etc/php/conf.d/`.

### Import fails partway (e.g. around 6%)

If the import starts then stops at a low percentage, the request is usually being cut off by **nginx** (body size or timeouts) or by **PHP** execution time. A common case is `client_max_body_size 100M` in the `location /` block — change it to `2G` and use longer proxy timeouts.

1. **Inspect the HTTPS server block** (the one that actually serves https://naba-wp-staging.herencia.build):

   ```bash
   cat /etc/nginx/sites-enabled/wordpress-staging
   ```

   Find the `server { ... }` block that contains `ssl_certificate` (and `server_name naba-wp-staging.herencia.build`). That block must include:
   - **In the `server` block (same level as `server_name`):** `client_max_body_size 2G;`
   - **In the `location /` block:** `proxy_read_timeout 3600;` `proxy_send_timeout 3600;` `proxy_connect_timeout 3600;` (or higher; 3600 = 1 hour)

2. **Edit the config** and add or adjust those directives. Example of what the HTTPS block should contain:

   ```nginx
   server {
       server_name naba-wp-staging.herencia.build;
       client_max_body_size 2G;

       location / {
           proxy_pass http://127.0.0.1:8080;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_read_timeout 3600;
           proxy_connect_timeout 3600;
           proxy_send_timeout 3600;
       }

       ssl_certificate ...;
       ssl_certificate_key ...;
       # ... rest of SSL config
   }
   ```

   **Quick fix** if your config has `client_max_body_size 100M` and `proxy_*_timeout 300` in the HTTPS block:

   ```bash
   sed -i 's/client_max_body_size 100M;/client_max_body_size 2G;/' /etc/nginx/sites-enabled/wordpress-staging
   sed -i 's/proxy_read_timeout 300;/proxy_read_timeout 3600;/' /etc/nginx/sites-enabled/wordpress-staging
   sed -i 's/proxy_connect_timeout 300;/proxy_connect_timeout 3600;/' /etc/nginx/sites-enabled/wordpress-staging
   # Add proxy_send_timeout if missing (optional)
   nginx -t && systemctl reload nginx
   ```

3. **Raise PHP execution time for the import** (so the unpack/import step doesn’t get killed). Re-write the container’s uploads.ini to use `max_execution_time = 0` (unlimited) for the long-running import:

   ```bash
   docker exec wordpress_staging bash -c 'echo "upload_max_filesize = 2G
   post_max_size = 2G
   memory_limit = 512M
   max_execution_time = 0
   max_input_time = 3600" > /usr/local/etc/php/conf.d/uploads.ini'
   docker compose restart wordpress
   ```

   (If you use a different container name, replace `wordpress_staging`.)

4. Retry the import. If it still fails at the same point, check Docker/disk space: `df -h` and `docker system df`.

### Import times out partway (e.g. 50%+)

If the import gets much further but then times out, either the **upload** (browser → nginx → PHP) or the **unpack/restore** step is hitting a timeout. Two approaches:

**A) Bump timeouts further and retry in browser**

- **Nginx:** Use 4-hour timeouts so a slow upload or long restore can finish. In the HTTPS `location /` block set:
  ```nginx
  proxy_read_timeout 14400;
  proxy_connect_timeout 14400;
  proxy_send_timeout 14400;
  ```
  (14400 seconds = 4 hours.) Then `nginx -t && systemctl reload nginx`.
- **PHP:** Ensure the container has `max_execution_time = 0` in `uploads.ini` (see step 3 above) and restart the WordPress container so the restore script is not killed mid-run.

**B) Import via SCP + WP-CLI (no browser, most reliable for large backups)**

1. **Copy the .wpress file into the container** (from your machine or from somewhere the server can reach):

   ```bash
   # From your laptop (replace with your .wpress path and server host)
   scp /path/to/backup.wpress root@142.93.177.21:/opt/wordpress-staging/
   ```

   On the server, put it into the plugin’s backup directory and fix ownership:

   ```bash
   cd /opt/wordpress-staging
   docker cp backup.wpress wordpress_staging:/var/www/html/wp-content/ai1wm-backups/
   # If the directory doesn’t exist, create it and retry:
   docker exec wordpress_staging mkdir -p /var/www/html/wp-content/ai1wm-backups
   docker cp backup.wpress wordpress_staging:/var/www/html/wp-content/ai1wm-backups/
   docker exec wordpress_staging chown -R www-data:www-data /var/www/html/wp-content/ai1wm-backups
   ```

2. **Run the restore via WP-CLI** (replace `backup.wpress` with the actual filename):

   ```bash
   docker exec -it wordpress_staging bash -c "cd /var/www/html && wp ai1wm restore backup.wpress --allow-root"
   ```

   If the plugin expects the file in a different path, run `wp ai1wm list-backups --allow-root` to see where it looks. The restore runs in the container with no browser or nginx timeouts.

3. After it finishes, log in at https://naba-wp-staging.herencia.build/wp-admin/ with your **production** credentials.

### Import fails at the very end

If the import runs almost to 100% then errors out, the failure is usually during the **final steps**: URL search-replace (production → staging), database finalization, or permalink flush. Try these in order:

1. **See if the site is already usable.** Open https://naba-wp-staging.herencia.build/ and try logging in at /wp-admin/ with your production credentials. If you get in, go to **Settings → Permalinks** and click **Save** (no need to change anything). Many “failed at the end” imports leave the site working; the plugin may have only missed the last cleanup step.

2. **Give PHP more memory for the final phase.** The plugin’s URL replace and DB writes can spike. Raise the container’s memory limit and keep execution unlimited:

   ```bash
   docker exec wordpress_staging bash -c 'echo "upload_max_filesize = 2G
   post_max_size = 2G
   memory_limit = 1024M
   max_execution_time = 0
   max_input_time = 3600" > /usr/local/etc/php/conf.d/uploads.ini'
   docker compose restart wordpress
   ```

   Then retry the import (browser or WP-CLI). Replace `wordpress_staging` if your container name is different.

3. **Raise MySQL limits** (in case the failure is during large option or post writes). Restart the DB container with a larger `max_allowed_packet` and longer timeouts. If you use `docker-compose.yml` from this doc, you can add to the `db` service:

   ```yaml
   command: --max_allowed_packet=256M --wait_timeout=28800 --interactive_timeout=28800
   ```

   Then `docker compose down` and `docker compose up -d`, wait for MySQL to be ready, and retry the import.

4. **Check disk space.** On the host: `df -h` and `docker system df`. If the volume or host is full, free space and run the import again.

5. **Retry the import once.** Sometimes a second run completes because most data is already there and the plugin only needs to finish the last steps.

### "Error establishing a database connection"

**Causes:**

- Database container not running
- Password mismatch between WordPress and MySQL config
- Database not properly initialized

**Fix:**

```bash
cd /opt/wordpress-staging

# Check if containers are running
docker compose ps

# If db is not running or unhealthy, recreate with fresh volumes
docker compose down -v
docker compose up -d

# Wait 45 seconds for MySQL to initialize
sleep 45
docker compose ps
```

### Server Freezes / SSH Disconnects

**Cause:** Insufficient memory (need at least 2GB RAM)

**Fix:**

1. Force reboot via DigitalOcean Control Panel (Power → Power cycle)
2. Upgrade droplet to 2GB RAM ($12/month)
3. After reboot, stop WordPress if needed:
   ```bash
   cd /opt/wordpress-staging
   docker compose down
   ```

### MySQL Connection Refused

If you see `Host 'xxx' is not allowed to connect`:

```bash
cd /opt/wordpress-staging
docker compose down -v  # Remove volumes to reset MySQL
docker compose up -d    # Recreate with fresh database
```

### Check What's Using Memory

```bash
docker stats --no-stream
```

### View All Containers

```bash
docker ps -a
```

## MemberPress Considerations

- **License:** May need separate staging license or deactivate on production temporarily
- **Payment Gateways:** Switch to sandbox/test mode in staging
- **Emails:** Disable transactional emails (use "Disable Emails" plugin)
- **Member Data:** Consider anonymizing member data in staging

## Related Services on This VPS

| Service           | Location               | Port | URL                                    |
| ----------------- | ---------------------- | ---- | -------------------------------------- |
| Listmonk          | /opt/listmonk          | 9000 | https://newsletter.herencia.build      |
| Umami             | /opt/umami             | 3000 | https://analytics.herencia.build       |
| WordPress Staging | /opt/wordpress-staging | 8080 | https://naba-wp-staging.herencia.build |

### Check All Services

```bash
cd /opt/listmonk && docker compose ps
cd /opt/umami && docker compose ps
cd /opt/wordpress-staging && docker compose ps
```

## Cleanup (If Needed)

To completely remove WordPress staging:

```bash
cd /opt/wordpress-staging
docker compose down -v
rm -rf /opt/wordpress-staging
rm /etc/nginx/sites-enabled/naba-staging
rm /etc/nginx/sites-available/naba-staging
nginx -t && systemctl reload nginx
```

---

## Quick Reference

```bash
# SSH in
ssh root@142.93.177.21

# Go to WordPress staging
cd /opt/wordpress-staging

# Status
docker compose ps

# Logs
docker compose logs -f wordpress

# Restart
docker compose restart

# Stop
docker compose down

# Start
docker compose up -d

# Memory check
free -h

# Enter WordPress shell
docker exec -it naba_staging bash
```
