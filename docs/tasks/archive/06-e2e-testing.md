# Task 6: End-to-End Integration Testing

## Objective

Validate the complete pipeline from WordPress staging through FastAPI to
the Astro frontend, document the deployment plan, and update project
documentation.

## Automated coverage (implemented)

From the repo root:

```bash
pip install -r requirements.txt
python -m pytest
```

- **`tests/test_public_api_schema_and_pii.py`** — No forbidden keys / email patterns in JSON; only public schema keys; non-public profiles excluded.
- **`tests/test_public_api_filters.py`** — `q`, `country`, `state_province`, `entry_type`, pagination; `/health` reports `data_source`.
- **`tests/test_sync_wordpress_idempotent.py`** — Sync `main()` twice with mocked WP payload; row counts unchanged.
- **`tests/test_sync_errors.py`** — Missing env and HTTP 401 produce clear `SystemExit` messages.
- **`tests/test_integration_e2e.py`** (skipped by default) — Set `RUN_INTEGRATION_E2E=1` and `WP_API_URL` / `WP_API_KEY` to assert `X-WP-Total` matches full MemberPress fetch; set `MEMBERSHIP_E2E_API_URL` to smoke-test a running API.

Manual curl parity: `bash scripts/e2e_manual_checks.sh` (requires `WP_API_URL`, `WP_API_KEY`, `API_BASE`).

Sections **2** (spot-check members in WP admin vs API/UI), **6** (visual browser checks), and parts of **7** (Astro fallback when API is down, WP down + cached SQLite) remain **manual**.

## Prerequisites

- Tasks 1–5 completed
- All three services running:
  - WordPress staging (Hostinger)
  - FastAPI (local or deployed)
  - Astro frontend (local or deployed)

## Test Plan

### 1. Data integrity tests

Verify that data in the Astro frontend matches what's in WordPress:

```bash
# Count members in WordPress
curl -s \
  -H "MEMBERPRESS-API-KEY: $WP_API_KEY" \
  "$WP_API_URL/members?per_page=1" \
  -D - -o /dev/null 2>/dev/null | grep -i x-wp-total

# Count members in FastAPI
curl -s "http://localhost:8000/api/v1/public/members?page_size=1" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])"
```

The counts should match (or the FastAPI count should equal the number of
**active** members in WP, since we filter by visibility).

### 2. Spot-check member data

Pick 3–5 members from WordPress admin and verify their data appears
correctly in the API and frontend:

| Check | Where | What to verify |
|-------|-------|----------------|
| Name | API response | `display_name` matches WP first+last name |
| Location | API response | `city`, `state_province`, `country` match WP address |
| Membership tier | API response | `role` or tags reflect active membership title |
| Member since | API response | `member_since_year` derived correctly |
| Website | API response | `website_url` matches WP user URL |
| Card display | Astro frontend | All fields render correctly on the card |

### 3. Privacy verification

Confirm that no PII leaks through the public API:

```bash
# Fetch a member from the public API
curl -s "http://localhost:8000/api/v1/public/members?page_size=1" \
  | python3 -m json.tool

# Verify these fields are NOT present:
# - email
# - street address (address line 1/2, zip code)
# - phone number
# - Stripe customer ID
# - transaction amounts
# - login count
```

### 4. Search and filter tests

```bash
# Search by name
curl -s "http://localhost:8000/api/v1/public/members?q=smith"

# Filter by country
curl -s "http://localhost:8000/api/v1/public/members?country=US"

# Filter by state
curl -s "http://localhost:8000/api/v1/public/members?state_province=CO"

# Filter by entry type
curl -s "http://localhost:8000/api/v1/public/members?entry_type=individual"

# Pagination
curl -s "http://localhost:8000/api/v1/public/members?page=2&page_size=10"
```

### 5. Sync re-run test

Verify that running the sync script again is idempotent:

```bash
# Run sync twice
python -m scripts.sync_from_wordpress
python -m scripts.sync_from_wordpress

# Member count should be the same
curl -s "http://localhost:8000/api/v1/public/members?page_size=1" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['total'])"
```

### 6. Frontend visual tests

Open `http://localhost:4321/directory` and verify:

- [ ] Member cards display correctly
- [ ] Membership Directory tab shows individuals/organizations
- [ ] Business Directory tab shows businesses (if any)
- [ ] Toggle between tabs works
- [ ] Cards show: name, role, location, website link, tags
- [ ] Empty states are handled gracefully
- [ ] Page loads reasonably fast (< 3 seconds for API fetch)

### 7. Error handling tests

- [ ] Stop the FastAPI server — Astro should fall back to static JSON
- [ ] Use invalid API key in `.env` — sync script should fail gracefully
  with a clear error message
- [ ] WordPress staging is down — sync script should fail with a
  connection error, but the FastAPI + SQLite should continue serving
  cached data

## Deployment Considerations

### Option A: Static build (current approach)

```
1. Run sync: python -m scripts.sync_from_wordpress
2. Export JSON: python -m scripts.export_directory_json
3. Build Astro: cd astro-app && npm run build
4. Deploy dist/ to Netlify
```

Pros: Simple, fast, no runtime API dependency.
Cons: Data is stale until next build.

### Option B: Runtime API

```
1. Deploy FastAPI to a host (Railway, Fly.io, Render, etc.)
2. Set PUBLIC_MEMBERSHIP_API_URL in Netlify env vars
3. Build and deploy Astro to Netlify
4. Client-side fetches hit the deployed API
```

Pros: Data is fresh (within sync frequency).
Cons: Requires API hosting, CORS config, uptime monitoring.

### Option C: Hybrid (recommended)

```
1. Deploy FastAPI service
2. Static build includes fallback JSON (via export script)
3. Client-side fetch overrides with live API data when available
4. Cron job runs sync periodically (daily or on webhook)
```

This is what the current `directory.astro` already supports — static
fallback with API overlay.

## Documentation Updates

After testing, update these files:

- [x] `README.md` — Add WordPress integration section, update workflow
- [x] `api/README.md` — Document new config options, sync script
- [x] `docs/plan-wp-frontend-integration.md` — Mark tasks as complete
- [x] Archive `docs/wordpress-staging-notes.md` → `docs/archive/wordpress-staging-notes.md` (old DigitalOcean staging)

## Deliverables

- [x] Automated test cases (privacy, filters, pagination, sync idempotency, sync errors) pass via `pytest`
- [x] No PII in public API responses (enforced in tests + `DirectoryProfilePublic` schema)
- [x] Sync script is idempotent and handles connection/HTTP errors with clear messages
- [ ] Frontend renders WP-sourced data correctly — verify manually (`/directory`, Task §2 and §6)
- [x] Deployment options documented (static / runtime API / hybrid — README + this doc)
- [x] README and docs updated
