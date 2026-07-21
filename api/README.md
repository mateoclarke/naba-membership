## NaBA Membership API

FastAPI service that exposes a **directory-safe membership API**. Data sources:

- **SQLite (default)** — `data/membership.db`, populated by `scripts.seed_members_from_csv` and/or `scripts.sync_from_wordpress`.
- **Live WordPress** — Set `DATA_SOURCE=wordpress` with `WP_API_URL` (MemberPress REST base, e.g. `https://…/wp-json/mp/v1`) and `WP_API_KEY` (`MEMBERPRESS-API-KEY` header value). The public list is built from MemberPress on each request (filtered to active + public visibility).

Environment variables are defined in the repo root `.env.schema` (recommended: `npx varlock run -- uvicorn api.main:app --reload`).

---

## Running the API

From the repo root (`naba-membership/`):

```bash
pip install -r requirements.txt

# Option A: seed from local CSVs (active members only)
python -m scripts.seed_members_from_csv

# Option B: pull from WordPress MemberPress API into SQLite
npx varlock run -- python -m scripts.sync_from_wordpress

# Start the API server
npx varlock run -- uvicorn api.main:app --reload
# or: uvicorn api.main:app --reload
```

Endpoints:

- Health check: `GET /health` — includes `data_source` and whether WP env vars are set.
- Public members: `GET /api/v1/public/members`

The API uses a local SQLite DB at `data/membership.db` (gitignored) when using the sqlite data source.

---

## Sync script (`scripts/sync_from_wordpress.py`)

- Paginates `GET {WP_API_URL}/members` with header `MEMBERPRESS-API-KEY: {WP_API_KEY}`.
- Replaces `members` and `directory_profiles` tables on each run (idempotent totals after re-run).
- On connection failure, HTTP errors (e.g. invalid key), or other request errors, exits with a **clear `SystemExit` message** instead of a raw stack trace.

---

## Tests

```bash
pip install -r requirements.txt
python -m pytest
```

Tests use an isolated temporary SQLite database (they do not touch `data/membership.db`). Optional WordPress checks: set `RUN_INTEGRATION_E2E=1` and credentials (see `tests/test_integration_e2e.py`).

---

## Data model (high level)

The API uses two main SQLAlchemy models (see `api/models.py`):

- `Member` (internal)
  - Mirrors useful parts of the MemberPress CSV and users export.
  - Contains PII (email, full name, address) and is **never** exposed directly via public endpoints.
  - Key fields:
    - `id` (MemberPress `ID`)
    - `first_name`, `last_name`, `email`
    - `status` (e.g. `active`, `expired`)
    - `memberships_raw` (raw membership codes)
    - `registered_at`, `first_txn_at`, `latest_txn_at`
    - `city`, `state_province`, `country`

- `DirectoryProfile` (public)
  - Derived from `Member` (and optionally WordPress user data).
  - Only contains **directory-safe** fields that can be returned by the public API.
  - Key fields:
    - `id` and `member_id` (numeric)
    - `display_name`
    - `entry_type` (`individual` | `organization` | `business`)
    - `role` (short text for directory card)
    - `organization` (optional org/business name)
    - `city`, `state_province`, `country`
    - `location_display` (formatted location string)
    - `website_url` (optional, one URL per profile)
    - `tags_csv` (comma-separated tags, parsed into an array at response time)
    - `member_since_year`
    - `visibility_public` (bool; only `True` rows are exposed)

The public API uses Pydantic models in `api/schemas.py`:

- `DirectoryProfilePublic` – JSON shape for a single directory entry.
- `PaginatedDirectoryProfiles` – wrapper for paged lists.

---

## Public endpoints

Defined in `api/routers_public_members.py`, mounted under `/api/v1/public/members`.

### `GET /api/v1/public/members`

List public directory profiles for active members.

Query parameters:

- `page` (default `1`, `>=1`)
- `page_size` (default `50`, max `500`)
- `q` – free-text search over name, organization, location, tags
- `entry_type` – filter by `individual`, `organization`, or `business`
- `country` – ISO country code (e.g. `US`, `CA`)
- `state_province` – region or state/province code (e.g. `CO`, `BC`)

Response shape:

```json
{
  "items": [
    {
      "id": 587,
      "display_name": "Mateo Salinas Clarke",
      "entry_type": "individual",
      "role": null,
      "organization": null,
      "city": "Taos",
      "state_province": "NM",
      "country": "US",
      "location_display": "Taos, NM (US)",
      "website_url": null,
      "tags": [],
      "member_since_year": 2023
    }
  ],
  "page": 1,
  "page_size": 50,
  "total": 123
}
```

Notes:

- Only rows with `visibility_public = True` are returned (currently seeded from **active** members only).
- `tags` is derived from the comma-separated `tags_csv` column.

---

## Seeding data

Script: `scripts/seed_members_from_csv.py`

Responsibilities:

- Create or update tables in `data/membership.db`.
- Read:
  - `data/NaBA Members.csv` (MemberPress export, local only)
  - `data/user-export-*.csv` (WordPress users export, local only; optional)
- For each **active** member:
  - Insert an internal `Member` row.
  - Derive a `DirectoryProfile` row:
    - `display_name` from first/last name and/or WordPress display name.
    - `member_since_year` from first transaction or registration date.
    - `location_display` from city/state/country.
    - `entry_type` currently defaults to `"individual"` (to be refined using membership XML/groups later).
    - `visibility_public` set to `True`.

The script is designed to be safe:

- It keeps all PII inside the local SQLite DB (ignored by git).
- It does **not** produce per-member JSON files or other artefacts that could accidentally be committed.