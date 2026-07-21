#!/usr/bin/env bash
# Smoke-check a deployed membership API.
# Usage: API_BASE=https://api.example.com bash scripts/smoke_prod_api.sh
set -euo pipefail

API_BASE="${API_BASE:?Set API_BASE to the API origin (no trailing slash)}"
API_BASE="${API_BASE%/}"

echo "== GET $API_BASE/health =="
curl -sS "$API_BASE/health" | tee /tmp/naba-health.json
echo

echo "== GET public members (anonymous; expect businesses) =="
curl -sS "$API_BASE/api/v1/public/members/?page=1&page_size=5" | tee /tmp/naba-members.json >/dev/null
python3 - <<'PY'
import json
data=json.load(open("/tmp/naba-members.json"))
types=sorted({i.get("entry_type") for i in data.get("items") or []})
print("total", data.get("total"), "entry_types", types)
if types and types != ["business"]:
    raise SystemExit("Expected anonymous list to be business-only")
print("ok: anonymous list is business-only (or empty)")
PY

echo "== GET map (anonymous; expect 401) =="
code=$(curl -sS -o /tmp/naba-map.json -w "%{http_code}" "$API_BASE/api/v1/public/members/map")
echo "status $code"
test "$code" = "401"

echo "Smoke checks passed."
