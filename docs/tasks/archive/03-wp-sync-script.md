# Task 3: Build WordPress → SQLite Sync Script

## Objective

Create a Python script that fetches member data from the MemberPress
REST API and writes it to the existing SQLite database, replacing or
augmenting the CSV-based seed script.

## Prerequisites

- Task 2 completed (API key stored in `.env`, API accessible)
- Existing codebase context:
  - `api/models.py` — SQLAlchemy models: `Member` (internal), `DirectoryProfile` (public)
  - `api/db.py` — Database setup (SQLite at `data/membership.db`)
  - `scripts/seed_members_from_csv.py` — Current CSV seeder (reference for field mapping)

## Architecture Decision

**Sync (pull) approach** — the script fetches all members from WordPress
and upserts them into SQLite. This is preferred over a live proxy because:

1. The Astro frontend can still build statically
2. No runtime dependency on WordPress uptime
3. The privacy filter (PII stripping) happens at sync time
4. Same FastAPI response shapes, no frontend changes needed

## Steps

### 1. Create `scripts/sync_from_wordpress.py`

The script should:

```
Read .env → fetch all members from WP API → map fields → upsert into SQLite
```

#### Core logic outline

```python
"""
Sync members from WordPress/MemberPress REST API into local SQLite.

Usage (with Varlock for validated env vars):
    npx varlock run -- python -m scripts.sync_from_wordpress

Or without Varlock (reads .env directly):
    python -m scripts.sync_from_wordpress

Requires .env with:
    WP_API_URL=https://....hostingersite.com/wp-json/mp/v1
    WP_API_KEY=your_api_key

Schema defined in .env.schema (committed to git).
"""

import os
import requests

# Varlock injects validated env vars into the process when run via
# `varlock run`. If running directly, fall back to reading .env.
WP_API_URL = os.environ["WP_API_URL"]
WP_API_KEY = os.environ["WP_API_KEY"]

# 2. Paginate through all members
def fetch_all_members():
    members = []
    page = 1
    while True:
        resp = requests.get(
            f"{WP_API_URL}/members",
            headers={"MEMBERPRESS-API-KEY": WP_API_KEY},
            params={"page": page, "per_page": 100},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        members.extend(batch)
        page += 1
    return members

# 3. Map WP member → internal Member + DirectoryProfile
def map_to_member(wp_member):
    """Map WP/MemberPress JSON → Member model fields."""
    ...

def map_to_directory_profile(wp_member):
    """Map WP/MemberPress JSON → DirectoryProfile model fields."""
    ...

# 4. Upsert into SQLite using existing models/db
def sync():
    members = fetch_all_members()
    # For each member: upsert Member, derive DirectoryProfile
    ...
```

### 2. Field mapping — Member (internal)

| WP field | Member column | Transform |
|----------|--------------|-----------|
| `id` | `id` | Direct |
| `first_name` | `first_name` | Direct |
| `last_name` | `last_name` | Direct |
| `email` | `email` | Direct |
| `active_txn_count` > 0 | `status` | `"active"` if has active txns, else check `expired_txn_count` |
| `active_memberships[*].title` | `memberships_raw` | Join titles with comma |
| `registered_at` | `registered_at` | Parse datetime |
| `first_txn.created_at` | `first_txn_at` | Parse datetime |
| `latest_txn.created_at` | `latest_txn_at` | Parse datetime (if available) |
| `address.mepr-address-city` | `city` | Direct |
| `address.mepr-address-state` | `state_province` | Direct |
| `address.mepr-address-country` | `country` | Direct |

### 3. Field mapping — DirectoryProfile (public)

| WP field(s) | DirectoryProfile column | Transform |
|-------------|------------------------|-----------|
| `id` | `member_id` | Direct |
| `first_name` + `last_name` | `display_name` | `f"{first} {last}".strip()` |
| (derived) | `entry_type` | Default `"individual"`, override based on membership title or custom field |
| `active_memberships[0].title` | `role` | Membership tier name |
| `profile.mepr_company_name` | `organization` | If present |
| `address.mepr-address-city` | `city` | Direct |
| `address.mepr-address-state` | `state_province` | Direct |
| `address.mepr-address-country` | `country` | Direct |
| (derived) | `location_display` | `"{city}, {state} ({country})"` |
| `url` | `website_url` | Validate URL |
| (derived) | `tags_csv` | From membership tier, country, custom fields |
| `first_txn.created_at` or `registered_at` | `member_since_year` | Extract year |
| `active_txn_count > 0` | `visibility_public` | `True` if active member |

### 4. Handle edge cases

- **No active memberships:** Set `visibility_public = False`
- **Missing address fields:** Leave location fields as `None`
- **Duplicate members:** Use `member_id` as upsert key (merge_on)
- **Deleted members:** Members in SQLite but not in WP should either be
  marked hidden or deleted (decide and document)
- **Rate limiting:** Add a small delay between paginated requests if the
  WP host throttles

### 5. Add `requests` to requirements

Update `requirements.txt`:

```
requests
```

Note: `python-dotenv` is no longer needed — Varlock handles env loading
and validation. The script reads from `os.environ` which Varlock
populates via `varlock run`.

### 6. Make it runnable

```bash
# Recommended: run via Varlock (validates env vars against .env.schema)
npx varlock run -- python -m scripts.sync_from_wordpress

# Alternative: source .env manually and run directly
source .env && python -m scripts.sync_from_wordpress
```

Output should print:
- Number of members fetched from WP
- Number of members upserted
- Number of directory profiles created/updated
- Any errors or skipped records

## Deliverables

- [ ] `scripts/sync_from_wordpress.py` created and working
- [ ] `requirements.txt` updated with `requests`
- [ ] `.env.schema` updated if any new env vars are needed (schema is
  the source of truth — no `.env.example` needed)
- [ ] Script successfully syncs staging members into `data/membership.db`
- [ ] Running `uvicorn api.main:app` after sync shows WP-sourced member
  data at `GET /api/v1/public/members`

## Relationship to Existing Code

- This script **replaces** `scripts/seed_members_from_csv.py` as the
  primary data source, but the CSV seeder should remain as a fallback
- Both scripts write to the same SQLite DB and same tables
- The FastAPI service (`api/`) is unchanged — it reads from SQLite
  regardless of how the data got there
