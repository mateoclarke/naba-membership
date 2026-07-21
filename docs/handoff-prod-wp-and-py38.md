# Handoff: Production WordPress datasource + Varlock + Python 3.8 fixes

**Date:** 2026-07-20  
**Branch context:** `wordpress` (local work; may be uncommitted)  
**Audience:** Fresh agent continuing NaBA membership work

## Goals completed in this session

1. Point the membership stack at **production WordPress** (MemberPress) instead of staging.
2. Set up **Varlock multi-env** (Approach B: `.env.test` / `.env.prod` selected via `APP_ENV`).
3. Unblock **uvicorn on Python 3.8** (multiple typing/runtime incompatibilities).
4. Clarify how **`AUTH_JWT_SECRET`** works and how to confirm the directory uses prod-backed data.

---

## Architecture reminder (unchanged)

```
WordPress (MemberPress REST)  →  sync script  →  SQLite (data/membership.db)
                                      ↓
                              FastAPI (uvicorn :8000)
                                      ↓
                         Astro directory (client fetch in browser)
```

- Default: `DATA_SOURCE=sqlite` — API reads SQLite; sync fills it from `WP_API_URL` / `WP_API_KEY`.
- Alternate: `DATA_SOURCE=wordpress` — API proxies MemberPress live (no DB for public list reads).
- Astro `directory.astro` ships static JSON fallback, then **replaces** the grid by fetching `GET /api/v1/public/members/` when `apiBaseUrl` is set (in DEV defaults to `http://localhost:8000`).

---

## Varlock multi-env (Approach B)

### Schema changes (`.env.schema`)

- Added `# @envFlag=APP_ENV` — **must be `APP_ENV`, not `$APP_ENV`** (Varlock 0.0.2 treats `$APP_ENV` as a literal key name and fails).
- Declared:
  ```env
  # @type=enum(development, test, staging, production)
  APP_ENV=development
  ```
- Changed `AUTH_JWT_EXPIRE_SECONDS` from `@type=integer` → `@type=number` (this Varlock build rejects `integer`).

### Env files (gitignored; do not commit)

| File | `APP_ENV` | Purpose |
|------|-----------|---------|
| `.env.test` | `test` | Staging / Hostinger WP |
| `.env.prod` | `production` | Production WP (`natural-building-alliance.org`) |

Varlock maps **`.env.prod` → `production`** (alias: `prod` → `production`).

Also gitignored: `.env.development`, `.env.staging`, `.env.production`, `.env.prod`, `.env.test`, etc. (see `.gitignore`).

### How to run

```bash
# Validate
APP_ENV=production npx varlock load
APP_ENV=test npx varlock load

# Sync from production MemberPress → SQLite
APP_ENV=production npx varlock run -- python -m scripts.sync_from_wordpress

# API
APP_ENV=production npx varlock run -- uvicorn api.main:app --reload
```

You can put `APP_ENV=production` in `.env` / `.env.local` to avoid prefixing every command.

### Production credentials (expected shape)

- `WP_API_URL=https://natural-building-alliance.org/wp-json/mp/v1`
- `WP_API_KEY=<prod MemberPress Developer Tools key>`
- Prefer `WP_SITE_URL=https://natural-building-alliance.org` for JWT login URL derivation (if still pointing at staging Hostinger, fix `.env.prod`).

---

## AUTH_JWT_SECRET — important clarification

**This is not a WordPress secret.** It is the FastAPI HS256 secret used to mint **API member session JWTs** after WP login (`api/security.py`).

- Look for it in **wherever the membership API is deployed** (env/secrets UI), not in WP admin.
- If the API was never deployed with it set, **generate a new one** and put it in both deploy env and `.env.prod`:
  ```bash
  openssl rand -base64 48
  ```
- Do not reuse a value that may have been committed or shared.

---

## Python 3.8 compatibility (why uvicorn was crashing)

User environment: **Python 3.8.10** via pyenv. Code had 3.9+/3.10+ typing that FastAPI/Pydantic evaluate at import time.

### Fixes applied

| Issue | Fix |
|-------|-----|
| `set[str]` / `list[str]` in `schemas.py` | `from __future__ import annotations` |
| `from typing import Annotated` | `from typing_extensions import Annotated` + `typing_extensions` in `requirements.txt` |
| `response_model=list[...]` (evaluated immediately) | `List[...]` from `typing` |
| `str \| None` / `list[UploadFile]` in FastAPI params | `Optional[...]` / `List[UploadFile]` |
| Broader `|` unions in API modules | Replaced with `Optional[...]` where needed |

**Key files touched:**  
`api/schemas.py`, `api/security.py`, `api/routers_admin_connect.py`, `api/routers_me.py`, `api/routers_admin.py`, `api/routers_admin_business_members.py`, `api/routers_public_members.py`, `api/routers_public_connect.py`, `api/profile_uploads.py`, `api/wp_client.py`, `api/auth_wp.py`, `api/slug.py`, `requirements.txt`

**Verified:** `python3.8 -c "from api.main import create_app; create_app()"` OK; `pytest` → 42 passed, 2 skipped.

**Ongoing constraint:** On 3.8, avoid `|` unions and builtin generics (`list[...]`, `dict[...]`) in **anything FastAPI inspects** (route params, `Depends`, `response_model=`). Prefer `Optional`, `List`, `Dict` from `typing`, or upgrade to **Python 3.10+** (recommended; 3.8 is EOL).

---

## Confirming the directory uses production-backed data

URL `http://localhost:4321/directory?view=members` — **`view=` only toggles UI section**; it does not select datasource.

### Data path in local dev

1. Astro (DEV) → `http://localhost:8000/api/v1/public/members/`
2. FastAPI with `DATA_SOURCE=sqlite` → **`data/membership.db`**
3. That DB is “prod” **only if** last sync used production `WP_API_URL` / key

Public list is **filtered** (opt-in / visibility), so totals will be **lower** than raw MemberPress fetch counts (e.g. sync ~580 vs public total often much smaller).

### Checks

```bash
curl -sS http://127.0.0.1:8000/health
# expect: data_source=sqlite, wp_api_configured=true

curl -sS 'http://127.0.0.1:8000/api/v1/public/members/?page=1&page_size=1'
# inspect total + a known prod-only profile
```

In browser DevTools → Network: confirm requests go to localhost:8000 (not only static JSON). If the API fetch fails, the page keeps **static** `astro-app/public/data/directoryEntries.json` (may be stale).

---

## Commands cheat sheet

```bash
# Prod sync + API
APP_ENV=production npx varlock run -- python -m scripts.sync_from_wordpress
APP_ENV=production npx varlock run -- uvicorn api.main:app --reload

# Astro (separate terminal)
cd astro-app && npm run dev
# → http://localhost:4321/directory?view=members
```

---

## Open / follow-ups for next agent

- [ ] Confirm `.env.prod` has correct **`WP_SITE_URL`** (prod origin, not Hostinger staging).
- [ ] Confirm **`AUTH_JWT_SECRET`** for real prod API deploy (generate if missing).
- [ ] Prefer upgrading local Python to **3.10+** to stop fighting typing backports.
- [ ] Optionally rename `.env.prod` → `.env.production` for clarity (both work with Varlock if `APP_ENV=production`).
- [ ] After sync, optionally re-export static JSON: `python -m scripts.export_directory_json` if static fallback should match prod.
- [ ] Deploy story for FastAPI + Netlify `PUBLIC_MEMBERSHIP_API_URL` still separate from local Varlock files.

## Docs / code pointers

- Env contract: `.env.schema`
- Sync: `scripts/sync_from_wordpress.py`
- Public members + filters: `api/routers_public_members.py`
- Directory hybrid fetch: `astro-app/src/pages/directory.astro` (`apiBaseUrl`, `fetchAllPublicMembers`)
- README: Varlock `APP_ENV` workflow section
- Staging WP notes (historical): `docs/WORDPRESS_STAGING_SETUP.md`
