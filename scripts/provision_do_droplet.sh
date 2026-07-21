#!/usr/bin/env bash
# Create a DigitalOcean droplet for the NaBA membership API (optional helper).
# Requires: DIGITALOCEAN_ACCESS_TOKEN, and an SSH key already in your DO account.
#
# Usage:
#   export DIGITALOCEAN_ACCESS_TOKEN=...
#   export NABA_DOMAIN=api.members.example.com   # DNS you will point at the droplet
#   bash scripts/provision_do_droplet.sh
set -euo pipefail

TOKEN="${DIGITALOCEAN_ACCESS_TOKEN:?Set DIGITALOCEAN_ACCESS_TOKEN}"
NABA_DOMAIN="${NABA_DOMAIN:?Set NABA_DOMAIN (hostname you will DNS to this droplet)}"
REGION="${DO_REGION:-nyc3}"
SIZE="${DO_SIZE:-s-1vcpu-1gb}"
IMAGE="${DO_IMAGE:-ubuntu-24-04-x64}"
NAME="${DO_DROPLET_NAME:-naba-membership-api}"

echo "Looking up SSH keys on the account…"
KEYS_JSON=$(curl -fsS -H "Authorization: Bearer $TOKEN" https://api.digitalocean.com/v2/account/keys)
KEY_IDS=$(python3 -c 'import json,sys; d=json.load(sys.stdin); ids=[str(k["id"]) for k in d.get("ssh_keys") or []];
print(",".join(ids));
assert ids, "No SSH keys on the DigitalOcean account — add one in the DO control panel first."' <<<"$KEYS_JSON")
echo "Using SSH key id(s): $KEY_IDS"

USER_DATA=$(cat <<EOF
#!/bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git curl ca-certificates
export NABA_DOMAIN=${NABA_DOMAIN}
export NABA_REPO=https://github.com/mateoclarke/naba-membership.git
export NABA_BRANCH=main
curl -fsSL https://raw.githubusercontent.com/mateoclarke/naba-membership/main/scripts/droplet_bootstrap.sh | bash
EOF
)

# DO API expects user_data as a string; pass via temp file JSON
PAYLOAD=$(python3 - <<PY
import json, os
key_ids = [int(x) for x in "${KEY_IDS}".split(",") if x]
print(json.dumps({
  "name": "${NAME}",
  "region": "${REGION}",
  "size": "${SIZE}",
  "image": "${IMAGE}",
  "ssh_keys": key_ids,
  "backups": False,
  "ipv6": True,
  "monitoring": True,
  "tags": ["naba-membership", "api"],
  "user_data": """${USER_DATA}""",
}))
PY
)

echo "Creating droplet ${NAME} (${SIZE} / ${REGION})…"
RESP=$(curl -fsS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  https://api.digitalocean.com/v2/droplets)

DROPLET_ID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["droplet"]["id"])' <<<"$RESP")
echo "Droplet id: $DROPLET_ID — waiting for public IPv4…"

IP=""
for _ in $(seq 1 60); do
  sleep 5
  D=$(curl -fsS -H "Authorization: Bearer $TOKEN" "https://api.digitalocean.com/v2/droplets/$DROPLET_ID")
  IP=$(python3 -c 'import json,sys
d=json.load(sys.stdin)["droplet"]
nets=d.get("networks",{}).get("v4",[])
pubs=[n["ip_address"] for n in nets if n.get("type")=="public"]
print(pubs[0] if pubs else "")' <<<"$D")
  if [[ -n "$IP" ]]; then
    break
  fi
  echo "  still provisioning…"
done

if [[ -z "$IP" ]]; then
  echo "Timed out waiting for IPv4. Check the DO control panel for droplet $DROPLET_ID" >&2
  exit 1
fi

echo
echo "Droplet is up."
echo "  IP:     $IP"
echo "  Name:   $NAME"
echo "  Domain: $NABA_DOMAIN"
echo
echo "Next:"
echo "  1) Create DNS A record: $NABA_DOMAIN → $IP"
echo "  2) SSH: ssh root@$IP   # cloud-init may still be running bootstrap (2–5 min)"
echo "  3) Edit secrets: nano /etc/naba-membership.env  (set WP_API_KEY, CORS_ORIGINS)"
echo "  4) systemctl restart naba-membership.api"
echo "  5) Initial sync (see docs/deploy-digitalocean-droplet.md)"
echo "  6) Set Netlify PUBLIC_MEMBERSHIP_API_URL=https://$NABA_DOMAIN"
