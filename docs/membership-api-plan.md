## NaBA Membership API – Design Plan

This document outlines a plan for a **mock (but potentially real)** membership API backed by the `data/NaBA Members.csv` export, designed to:

- Power the Astro directory at `astro-app/src/pages/directory.astro`
- Respect member privacy and avoid committing sensitive data
- Be swappable with a future WordPress headless API (same response shapes)

The assumption is that this service may become a long‑term alternative to a WordPress API if needed.

---

## Goals

- **Public directory API** for members, organizations, and businesses:
  - Supports the current `DirectoryEntry` shape in `directory.astro`
  - Adds room for richer public fields (bio, website, tags, services, etc.)
- **Strict privacy**:
  - No emails, street addresses, Stripe IDs, or raw transaction history in public responses
  - No per‑member JSON snapshots with PII committed to Git
- **Replaceable backend**:
  - API contracts that could be served by either:
    - This CSV‑backed service, or
    - A future WordPress headless API (or another system)

---

## Data model

### 1. Source data (CSV)

`data/NaBA Members.csv` appears to be a MemberPress export with fields like:

- Identifiers: `ID`, `username`, `email`, `name`, `first_name`, `last_name`
- Activity: `status` (active/expired/none), transaction counts, `total_spent`, `first_txn_date`, `latest_txn_date`
- Memberships: `memberships`, `inactive_memberships`
- Auth: `last_login_date`, `login_count`
- Address: `mepr-address-one`, `mepr-address-two`, `mepr-address-city`, `mepr-address-country`, `mepr-address-state`, `mepr-address-zip`
- Payment: Stripe customer id (`_mepr_stripe_customer_id_*`)

These contain **PII and payment identifiers** that must not be exposed publicly.

### 2. Internal vs public schema

Split the model into two conceptual layers:

- **Internal member record** (not exposed via public API)
  - Mirrors most of the CSV fields, plus some derived fields:
    - `member_id` (stable numeric / UUID)
    - `email`, `first_name`, `last_name`, address fields
    - `status`, `memberships`, `first_txn_date`, `latest_txn_date`, `total_spent`, `login_count`, etc.
    - `source_system` (e.g. `"memberpress_csv"` vs future `"wordpress_api"`)
  - Stored only in a local database (e.g. SQLite/Postgres) **ignored by Git**

- **Public directory profile** (what the API returns for front‑end)
  - Minimal, directory‑safe fields:
    - `id`: public member ID (can be same as `member_id` or a separate slug)
    - `display_name`: string – e.g. `"Harmony LeMaire"` or organization name
    - `entry_type`: `'individual' | 'organization' | 'business'`
    - `role`: short line for directory card (e.g. `Natural builder`, `Plaster contractor`, `Nonprofit`)
    - `organization`: optional org/business name
    - `city`: optional
    - `state_province`: optional
    - `country`: optional (2‑letter or full name)
    - `location_display`: formatted for UI, e.g. `"Sebastopol, CA (US)"`
    - `website_url`: optional (safe URL users explicitly approve)
    - `tags`: array of strings (skills, materials, services, regions, etc.)
    - `member_since_year`: derived from first transaction / registration date
    - `visibility`: `'public' | 'members_only' | 'hidden'`
  - **Explicitly excluded**: email, phone, street address lines, postal code, Stripe IDs, transaction counts, `total_spent`.

We can materialize a **`directory_profiles`** table/view that is derived from the internal member table but only stores/serves allowed fields.

### 3. Extra attributes to add (not in CSV)

We likely need additional attributes beyond what’s in the CSV to make a useful directory:

- **Display/consent**
  - `visibility` – whether this profile is public, members‑only, or hidden
  - `opt_in_directory` – boolean flag for directory inclusion (default `false` if in doubt)

- **Narrative & context**
  - `short_bio` – 1–2 sentences about the member or organization
  - `skills` / `materials` – e.g. `["straw bale", "earthen plasters"]`
  - `services_offered` – e.g. `["design", "consulting", "workshops"]`
  - `regions_served` – e.g. `["Colorado Front Range", "Southwest US"]`

- **URLs & social**
  - `website_url`
  - `instagram`, `facebook`, `other_social` (optional)

- **Classification**
  - `entry_type` – `'individual' | 'organization' | 'business'`
  - `membership_tier` – e.g. `"Supporter"`, `"Professional"`, `"Organization"`, `"Lifetime"` (derived from `memberships` codes)

We can start with a **minimal public profile** (name, type, city/state/country, website, tags) and leave the richer fields to be populated later via admin tooling or additional imports.

---

## API shape (v1)

Base URL (dev): `http://localhost:8000/api`

### Public endpoints

All return **directory‑safe fields only**.

- `GET /api/v1/public/members`
  - Query params:
    - `page`, `page_size`
    - `q` – free‑text search (name, org, tags, location)
    - `entry_type` – filter by `'individual' | 'organization' | 'business'`
    - `country`, `state`, `region`
    - `membership_status` – e.g. `"active"` or `"expired"` (optional)
  - Response:
    - `items: DirectoryProfile[]`
    - `page`, `page_size`, `total`

- `GET /api/v1/public/members/:id`
  - Detail view for one public profile.

- `GET /api/v1/public/stats`
  - Aggregated counts only (no PII), e.g.:
    - `members_by_state`
    - `members_by_country`
    - `members_by_entry_type`

### Future admin / private endpoints

These would require auth and **are not needed immediately**, but the design should leave room for:

- `GET /api/v1/admin/members` – internal fields for admin UI
- `POST/PUT /api/v1/admin/members/:id` – edit directory profile (bio, website, tags, visibility)
- Webhook / import endpoints to accept data from WordPress or other systems later.

---

## Implementation approach

### 1. Tech stack

Given this repo already uses Python for data scripts, a reasonable choice is:

- **Backend:** Python **FastAPI** + Uvicorn
- **Data storage:** SQLite for dev (single file, `.gitignore`d), with a clear path to Postgres later
- **Data import:** one‑off script under `scripts/` to seed from `data/NaBA Members.csv`

Alternative: Node/Express or a serverless function stack, but FastAPI aligns with the existing Python tooling and is easy to containerize if desired.

### 2. Data seeding from CSV

Create a script like `scripts/seed_members_from_csv.py` that:

1. Reads `data/NaBA Members.csv` using `pandas` or Python’s `csv` module.
2. For each row:
   - Creates/updates an internal `members` row with:
     - `member_id` (from CSV `ID`)
     - Raw fields we need internally (status, membership codes, dates, address, etc.)
   - Populates or updates a `directory_profiles` row with:
     - `id` (same as `member_id` or a derived slug)
     - `display_name` (e.g. `"First Last"` from `first_name` + `last_name`)
     - `entry_type` – initially default to `'individual'` and allow overrides later
     - `location_display` – built from city/state/country
     - `country`, `state_province`, `city`
     - `member_since_year` – from `first_txn_date` or `registered`
     - `visibility` – initially `'hidden'` or `'public'` for **active** members only, based on your preference
     - `tags` – maybe simple derived tags like `"US"`, `"Canada"`, `"International"` plus membership tier tags
3. Never write emails, Stripe IDs, or full addresses into the `directory_profiles` table.
4. Writes to a local SQLite database file (e.g. `data/membership.db`) that is **ignored by Git**.

We can also create a tiny **synthetic sample DB** for tests with anonymized records checked into `tests/` without real PII, if needed.

### 3. API service layout

Proposed structure:

```text
api/
  main.py            # FastAPI app
  models.py          # SQLAlchemy models / Pydantic schemas
  db.py              # DB session / engine setup
  routers/
    public_members.py
    admin_members.py (future)
  config.py          # env config (DB url, CORS, etc.)
```

Key pieces:

- `DirectoryProfile` Pydantic model that matches what Astro needs.
- SQLAlchemy models for `Member` (internal) and `DirectoryProfile` (public).
- CORS enabled for `http://localhost:4321` (Astro dev server).

### 4. Integration with Astro directory

The current `directory.astro` reads from a static JSON file:

```ts
import entriesData from '../../public/data/directoryEntries.json';
```

Two integration paths:

1. **Static build integration** (simple, good for Netlify/SSG)
   - Add a small Node or Python build script that:
     - Calls `GET /api/v1/public/members` at build time.
     - Writes the response to `astro-app/public/data/directoryEntries.json` (same shape as now).
   - Astro remains fully static; the API only needs to be reachable when building.

2. **Runtime integration** (dynamic directory)
   - Convert `directory.astro` to fetch data from the API at runtime (e.g. via `fetch` in Astro server‑side).
   - Requires the API to be deployed and reachable from the Astro host.

Initially, option **(1)** is simpler: keep the same front‑end shape and just swap where the JSON comes from.

---

## Privacy & repository hygiene

- Keep **source CSVs** (`data/NaBA Members.csv`, etc.) already in the repo, but do **not** commit:
  - Generated DB files (`*.db`, `*.sqlite`)
  - Per‑member JSON exports
  - Logs that contain emails or addresses
- Enforce this via:
  - `.gitignore` entries for `data/*.db`, `data/*.sqlite`, `api/*.db`, etc.
  - Keeping the public API schemas PII‑free by design.
- If we later add an admin UI, host it separately behind authentication and never expose those endpoints publicly.

---

## Open questions for you

Please clarify these so we can refine the plan and then implement:

1. **Visibility defaults (DECIDED):** Only **active** members appear in the public directory; others (expired/none) are hidden and only visible in a future admin view.
2. **Directory scope (DECIDED):** Public directory includes:
   - **Membership Directory:** individuals and organizations.
   - **Business Directory:** businesses or sole proprietors. A member profile can choose to appear in the Business Directory either as an individual with specialties or by creating a related Business entry.
3. **Public contact info (DECIDED):** It is acceptable to show **city + state + country** in public profiles.
4. **Website & social (DECIDED):** Support **one website URL** in the public API; members can choose to use their site, Facebook, Instagram, etc., for that URL.
5. **Tech stack (DECIDED):** Implement the service with **Python/FastAPI**, backed by a local SQLite DB (or Postgres later), seeded from `data/NaBA Members.csv`.

Next step: implement the FastAPI skeleton (`api/` directory), define the `DirectoryProfile` schema and filters according to these decisions, and add the `scripts/seed_members_from_csv.py` importer that creates internal member records and public directory profiles without exposing PII in the repo.

