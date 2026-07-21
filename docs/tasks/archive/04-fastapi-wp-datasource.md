# Task 4: Add WordPress Data Source Configuration to FastAPI

## Objective

Update the FastAPI service to support configurable data sources, add
environment-based configuration, and optionally support a live WordPress
proxy mode alongside the existing SQLite-backed mode.

## Prerequisites

- Task 3 is **not** a hard dependency: default `DATA_SOURCE=sqlite` reads whatever is in SQLite (CSV seed, manual data, or data from Task 3’s sync). Task 3 is the intended production path for WP-sourced data, but this task’s code does not call the sync script.
- Existing codebase:
  - `api/main.py` — FastAPI app creation, CORS, router mounting
  - `api/db.py` — SQLite engine/session setup
  - `api/routers_public_members.py` — Public members endpoint
  - `api/schemas.py` — Pydantic response models
  - `api/models.py` — SQLAlchemy ORM models

## Steps

### 1. Add environment configuration

Create `api/config.py` to centralize configuration. When running via
`npx varlock run -- uvicorn api.main:app`, Varlock validates env vars
against `.env.schema` and injects them into the process. The config
module reads from `os.environ` with sensible defaults for any optional
vars:

```python
"""
Application configuration from environment variables.

Env vars are validated by Varlock (.env.schema) when using:
    npx varlock run -- uvicorn api.main:app --reload
"""
import os

# WordPress API (used by sync script and optional live proxy)
WP_API_URL = os.environ.get("WP_API_URL", "")
WP_API_KEY = os.environ.get("WP_API_KEY", "")

# Data source mode: "sqlite" (default) or "wordpress" (live proxy)
DATA_SOURCE = os.environ.get("DATA_SOURCE", "sqlite")

# CORS origins (comma-separated)
CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:4321,http://127.0.0.1:4321"
).split(",")
```

### 2. Update CORS configuration

In `api/main.py`, replace the hardcoded origins list with the
config-driven one:

```python
from .config import CORS_ORIGINS

origins = [o.strip() for o in CORS_ORIGINS if o.strip()]
```

Add the Astro production URL and any staging URLs to the `.env`:

```
CORS_ORIGINS=http://localhost:4321,http://127.0.0.1:4321,https://your-astro-site.netlify.app
```

### 3. (Optional) Add live WordPress proxy mode

If `DATA_SOURCE=wordpress`, the `/api/v1/public/members` endpoint could
fetch directly from the MemberPress API instead of SQLite. This is
optional — the sync approach from Task 3 is the primary path.

If implementing the proxy:

- Create `api/wp_client.py` with a `MemberPressClient` class
- Add a dependency in the router that selects the data source based on
  config
- Map WP responses to the existing `DirectoryProfilePublic` schema
  server-side (so the Astro frontend sees the same shape)

```python
# api/wp_client.py (sketch)
import httpx
from .config import WP_API_URL, WP_API_KEY

class MemberPressClient:
    def __init__(self):
        self.base_url = WP_API_URL
        self.headers = {"MEMBERPRESS-API-KEY": WP_API_KEY}

    async def get_members(self, page=1, per_page=50):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/members",
                headers=self.headers,
                params={"page": page, "per_page": per_page},
            )
            resp.raise_for_status()
            return resp.json()
```

### 4. Add a health check that reports data source

Update the `/health` endpoint to show which data source is active:

```python
@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "data_source": config.DATA_SOURCE,
        "wp_api_configured": bool(config.WP_API_URL),
    }
```

### 5. Verify `.env.schema` is up to date

The `.env.schema` file (committed to git) is the single source of truth
for all environment variables. It replaces `.env.example`. Verify it
includes all vars used in `api/config.py`:

```env-spec
# @defaultSensitive=false
# @defaultRequired=false
# ---

# @type=url(prependHttps=true) @required
WP_API_URL=

# @type=string @required @sensitive
WP_API_KEY=

# @type=enum(sqlite, wordpress)
DATA_SOURCE=sqlite

# @type=string
CORS_ORIGINS=http://localhost:4321,http://127.0.0.1:4321

# @type=url(prependHttps=true)
PUBLIC_MEMBERSHIP_API_URL=http://localhost:8000
```

### 6. Update `requirements.txt`

Add any new dependencies:

```
httpx          # only if implementing async WP proxy
```

Note: `python-dotenv` is no longer needed — Varlock handles env loading.

## Deliverables

- [ ] `api/config.py` created with environment-based configuration
- [ ] `api/main.py` updated to use config for CORS origins
- [ ] `/health` endpoint reports data source status
- [ ] `.env.schema` is up to date and committed (replaces `.env.example`)
- [ ] `.gitignore` includes `.env`, `.env.local`, `.env.*.local`
- [ ] (Optional) `api/wp_client.py` for live proxy mode
- [ ] `requirements.txt` updated

## Testing

```bash
# Start the API with Varlock (validates env vars first)
npx varlock run -- uvicorn api.main:app --reload

# Verify health
curl http://localhost:8000/health
# → {"status":"ok","data_source":"sqlite","wp_api_configured":true}

# Verify members endpoint returns WP-sourced data
curl "http://localhost:8000/api/v1/public/members?page_size=5" | python3 -m json.tool
```
