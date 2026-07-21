# Deploy membership API on a DigitalOcean Droplet

Target: always-on FastAPI + SQLite (`data/membership.db`) + daily MemberPress sync.
Frontend stays on Netlify; set `PUBLIC_MEMBERSHIP_API_URL` to this API’s HTTPS origin.

**Production hostname:** `https://api.natbuild.org`  
**Droplet (current):** `142.93.177.21` (shared with listmonk / umami on `*.herencia.build`)

Suggested size if creating a dedicated box: **Basic droplet, 1 GB RAM / 1 vCPU (~$6/mo)**, Ubuntu 24.04 LTS.

## DNS (required before TLS)

At the DNS host for **natbuild.org** (Namecheap → NS1), create:

| Type | Host | Value |
|------|------|-------|
| A | `api` | `142.93.177.21` |

Optional apex/www for the marketing site is separate; the membership API only needs `api`.

After DNS propagates:

```bash
ssh root@142.93.177.21 'certbot --nginx -d api.natbuild.org --non-interactive --agree-tos --register-unsafely-without-email --redirect'
```

## 1. Create the droplet (if not using the existing host)

1. DigitalOcean → Create → Droplets → Ubuntu 24.04 → Basic $6.
2. Add your SSH key. Region near your users (e.g. NYC / SFO).
3. Networking → Firewall: allow **22**, **80**, **443** only.
4. Point DNS A record `api.natbuild.org` at the droplet IP.

## 2. Bootstrap on the server

```bash
export NABA_DOMAIN=api.natbuild.org
export NABA_REPO=https://github.com/mateoclarke/naba-membership.git
export NABA_BRANCH=main
sudo bash scripts/droplet_bootstrap.sh
```

## 3. Production env

`/etc/naba-membership.env` (mode `600`):

```bash
APP_ENV=production
DATA_SOURCE=sqlite
WP_API_URL=https://natural-building-alliance.org/wp-json/mp/v1
WP_API_KEY=REPLACE_ME
WP_SITE_URL=https://natural-building-alliance.org
AUTH_JWT_SECRET=REPLACE_ME
ADMIN_API_KEY=REPLACE_ME
CORS_ORIGINS=https://naba-membership.netlify.app,https://members.natbuild.org,https://natbuild.org,http://natbuild.org
UPLOADS_ROOT=/var/www/naba-membership/uploads
```

```bash
sudo systemctl restart naba-membership.api
sudo bash -c 'set -a; source /etc/naba-membership.env; set +a; cd /var/www/naba-membership && sudo -E -u www-data .venv/bin/python -m scripts.sync_from_wordpress'
```

## 4. Netlify (Astro)

| Variable | Value |
|----------|-------|
| `PUBLIC_MEMBERSHIP_API_URL` | `https://api.natbuild.org` |
| `PUBLIC_JOIN_MEMBERSHIP_URL` | `https://natural-building-alliance.org/register/` |

## 5. Smoke checks

```bash
API_BASE=https://api.natbuild.org bash scripts/smoke_prod_api.sh
```

## Unit / nginx files

- [`deploy/naba-membership.api.service`](../deploy/naba-membership.api.service)
- [`deploy/nginx-naba-api.conf`](../deploy/nginx-naba-api.conf)
- [`scripts/droplet_bootstrap.sh`](../scripts/droplet_bootstrap.sh)
