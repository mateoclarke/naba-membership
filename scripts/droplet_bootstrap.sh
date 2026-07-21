#!/usr/bin/env bash
# Bootstrap NaBA membership API on an Ubuntu DigitalOcean droplet.
# Usage (as root):
#   NABA_DOMAIN=api.example.com bash scripts/droplet_bootstrap.sh
set -euo pipefail

NABA_DOMAIN="${NABA_DOMAIN:?Set NABA_DOMAIN to the API hostname (DNS A record must point here)}"
NABA_REPO="${NABA_REPO:-https://github.com/mateoclarke/naba-membership.git}"
NABA_BRANCH="${NABA_BRANCH:-main}"
APP_ROOT="${APP_ROOT:-/var/www/naba-membership}"
ENV_FILE="${ENV_FILE:-/etc/naba-membership.env}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  python3 python3-venv python3-pip \
  nginx certbot python3-certbot-nginx \
  git curl ca-certificates

id -u www-data >/dev/null 2>&1 || useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin www-data

if [[ ! -d "$APP_ROOT/.git" ]]; then
  mkdir -p "$(dirname "$APP_ROOT")"
  git clone --branch "$NABA_BRANCH" "$NABA_REPO" "$APP_ROOT"
else
  git -C "$APP_ROOT" fetch origin
  git -C "$APP_ROOT" checkout "$NABA_BRANCH"
  git -C "$APP_ROOT" pull --ff-only origin "$NABA_BRANCH" || true
fi

mkdir -p "$APP_ROOT/data" "$APP_ROOT/uploads"
chown -R www-data:www-data "$APP_ROOT"

if [[ ! -d "$APP_ROOT/.venv" ]]; then
  sudo -u www-data python3 -m venv "$APP_ROOT/.venv"
fi
sudo -u www-data "$APP_ROOT/.venv/bin/pip" install --upgrade pip
sudo -u www-data "$APP_ROOT/.venv/bin/pip" install -r "$APP_ROOT/requirements.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  AUTH_JWT_SECRET="$(openssl rand -base64 48 | tr -d '\n')"
  ADMIN_API_KEY="$(openssl rand -base64 32 | tr -d '\n')"
  cat >"$ENV_FILE" <<EOF
APP_ENV=production
DATA_SOURCE=sqlite
WP_API_URL=https://natural-building-alliance.org/wp-json/mp/v1
WP_API_KEY=REPLACE_ME
WP_SITE_URL=https://natural-building-alliance.org
AUTH_JWT_SECRET=${AUTH_JWT_SECRET}
ADMIN_API_KEY=${ADMIN_API_KEY}
CORS_ORIGINS=https://naba-membership.netlify.app,https://members.natbuild.org,https://natbuild.org,http://natbuild.org
UPLOADS_ROOT=${APP_ROOT}/uploads
EOF
  chmod 600 "$ENV_FILE"
  echo "Created $ENV_FILE — edit WP_API_KEY before relying on prod."
else
  echo "Keeping existing $ENV_FILE"
fi

install -m 644 "$APP_ROOT/deploy/naba-membership.api.service" /etc/systemd/system/naba-membership.api.service
systemctl daemon-reload
systemctl enable naba-membership.api
systemctl restart naba-membership.api || systemctl start naba-membership.api

NGINX_SITE=/etc/nginx/sites-available/naba-membership-api
sed "s/NABA_DOMAIN/${NABA_DOMAIN}/g" "$APP_ROOT/deploy/nginx-naba-api.conf" >"$NGINX_SITE"
ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/naba-membership-api
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

certbot --nginx -d "$NABA_DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect || {
  echo "certbot failed (DNS may not point here yet). HTTP nginx is up; re-run:"
  echo "  certbot --nginx -d $NABA_DOMAIN"
}

CRON_FILE=/etc/cron.d/naba-membership-sync
cat >"$CRON_FILE" <<EOF
# Daily MemberPress → SQLite sync (06:00 UTC)
0 6 * * * www-data bash -c 'set -a; source ${ENV_FILE}; set +a; cd ${APP_ROOT} && ${APP_ROOT}/.venv/bin/python -m scripts.sync_from_wordpress' >> /var/log/naba-sync.log 2>&1
EOF
chmod 644 "$CRON_FILE"
touch /var/log/naba-sync.log
chown www-data:www-data /var/log/naba-sync.log

echo
echo "Bootstrap complete for https://${NABA_DOMAIN}"
echo "1) Edit secrets: nano $ENV_FILE"
echo "2) Restart API:  systemctl restart naba-membership.api"
echo "3) Initial sync: sudo bash -c 'set -a; source $ENV_FILE; set +a; cd $APP_ROOT && sudo -E -u www-data .venv/bin/python -m scripts.sync_from_wordpress'"
echo "4) Health:       curl -sS https://$NABA_DOMAIN/health || curl -sS http://$NABA_DOMAIN/health"
