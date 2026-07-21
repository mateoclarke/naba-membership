#!/usr/bin/env bash
# Manual checks from docs/tasks/06-e2e-testing.md (curl examples).
# Usage: export WP_API_URL, WP_API_KEY; ensure uvicorn is on API_BASE (default http://localhost:8000).

set -euo pipefail

API_BASE="${API_BASE:-http://localhost:8000}"

echo "=== WordPress X-WP-Total (first page) ==="
curl -sS \
  -H "MEMBERPRESS-API-KEY: ${WP_API_KEY:?set WP_API_KEY}" \
  "${WP_API_URL:?set WP_API_URL}/members?per_page=1" \
  -D - -o /dev/null 2>/dev/null | grep -i x-wp-total || true

echo "=== FastAPI public total ==="
curl -sS "${API_BASE}/api/v1/public/members?page_size=1" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])"

echo "=== Sample public payload (PII spot-check manually) ==="
curl -sS "${API_BASE}/api/v1/public/members?page_size=1" | python3 -m json.tool

echo "=== Search / filters / pagination ==="
curl -sS "${API_BASE}/api/v1/public/members?q=smith" | python3 -c "import sys,json; d=json.load(sys.stdin); print('q=smith total', d['total'])"
curl -sS "${API_BASE}/api/v1/public/members?country=US" | python3 -c "import sys,json; d=json.load(sys.stdin); print('country=US total', d['total'])"
curl -sS "${API_BASE}/api/v1/public/members?state_province=CO" | python3 -c "import sys,json; d=json.load(sys.stdin); print('state=CO total', d['total'])"
curl -sS "${API_BASE}/api/v1/public/members?entry_type=individual" | python3 -c "import sys,json; d=json.load(sys.stdin); print('entry_type=individual total', d['total'])"
curl -sS "${API_BASE}/api/v1/public/members?page=2&page_size=10" | python3 -c "import sys,json; d=json.load(sys.stdin); print('page2 size', len(d['items']), 'total', d['total'])"

echo "Done."
