# Deploy membership API on a DigitalOcean Droplet

Target: always-on FastAPI + SQLite (`data/membership.db`) + daily MemberPress sync.
Frontend stays on Netlify; set `PUBLIC_MEMBERSHIP_API_URL` to this API’s HTTPS origin.

Suggested size: **Basic droplet, 1 GB RAM / 1 vCPU (~$6/mo)**, Ubuntu 24.04 LTS.

## 1. Create the droplet

1. DigitalOcean → Create → Droplets → Ubuntu 24.04 → Basic $6.
2. Add your SSH key. Region near your users (e.g. NYC / SFO).
3. Networking → Firewall: allow **22**, **80**, **443** only.
4. Point a DNS A record at the droplet IP, e.g. `api.members.natbuild.org` (or any hostname you control).

## 2. Bootstrap on the server

SSH in as root (or a sudo user), then:

```bash
# As root
export NABA_DOMAIN=api.members.example.com   # your API hostname
export NABA_REPO=https://github.com/mateoclarke/naba-membership.git
export NABA_BRANCH=main

curl -fsSL https://raw.githubusercontent.com/mateoclarke/naba-membership/main/scripts/droplet_bootstrap.sh \
  | bash
```

Or clone first and run locally from the repo:

```bash
git clone https://github.com/mateoclarke/naba-membership.git /var/www/naba-membership
cd /var/www/naba-membership && git checkout main
sudo NABA_DOMAIN=api.members.example.com bash scripts/droplet_bootstrap.sh
```

The bootstrap script:

- Installs Python 3, nginx, certbot
- Creates `/var/www/naba-membership` venv + `pip install -r requirements.txt`
- Creates `/etc/naba-membership.env` from a template (you must edit secrets)
- Installs systemd unit `naba-membership.api`
- Configures nginx reverse proxy + Let’s Encrypt
- Installs a daily cron for `scripts.sync_from_wordpress`

## 3. Fill in production env

Edit `/etc/naba-membership.env` (mode `600`):

```bash
APP_ENV=production
DATA_SOURCE=sqlite
WP_API_URL=https://natural-building-alliance.org/wp-json/mp/v1
WP_API_KEY=REPLACE_ME
WP_SITE_URL=https://natural-building-alliance.org
AUTH_JWT_SECRET=REPLACE_ME          # openssl rand -base64 48
ADMIN_API_KEY=REPLACE_ME            # optional but recommended
CORS_ORIGINS=https://YOUR-NETLIFY-SITE.netlify.app,https://members.natbuild.org
UPLOADS_ROOT=/var/www/naba-membership/uploads
```

Then:

```bash
sudo systemctl restart naba-membership.api
sudo -u www-data bash -c 'set -a; source /etc/naba-membership.env; set +a; cd /var/www/naba-membership && .venv/bin/python -m scripts.sync_from_wordpress'
```

Schema reference: [`.env.schema`](../.env.schema).

## 4. Schema / “migrations”

No Alembic. On API start, `api.main:create_app` runs `Base.metadata.create_all` and `ensure_*` helpers (slug, geocode, categories/materials, `subscriptions_json`). Restarting the service after a deploy is enough.

## 5. Netlify (Astro)

Site settings → Environment variables (Production):

| Variable | Example |
|----------|---------|
| `PUBLIC_MEMBERSHIP_API_URL` | `https://api.members.example.com` |
| `PUBLIC_JOIN_MEMBERSHIP_URL` | `https://natural-building-alliance.org/register/` |

Trigger a new deploy. Align `CORS_ORIGINS` on the droplet with these exact origins (no trailing slash).

## 6. Smoke checks

```bash
curl -sS https://$NABA_DOMAIN/health
curl -sS "https://$NABA_DOMAIN/api/v1/public/members/?page_size=1"
curl -sS -o /dev/null -w "%{http_code}\n" https://$NABA_DOMAIN/api/v1/public/members/map
# expect 401 when anonymous
```

Browser:

1. Sign in on the Netlify site → redirects to membership directory.
2. Active members see directory + Map nav; inactive see renew prompt.
3. `/account/profile` shows subscription rows after sync.

## 7. Deploying code updates

```bash
cd /var/www/naba-membership
sudo -u www-data git fetch origin && sudo -u www-data git checkout main && sudo -u www-data git pull
sudo -u www-data /var/www/naba-membership/.venv/bin/pip install -r requirements.txt
sudo systemctl restart naba-membership.api
```

## Unit / nginx file locations (in repo)

- [`deploy/naba-membership.api.service`](../deploy/naba-membership.api.service)
- [`deploy/nginx-naba-api.conf`](../deploy/nginx-naba-api.conf)
- [`scripts/droplet_bootstrap.sh`](../scripts/droplet_bootstrap.sh)
