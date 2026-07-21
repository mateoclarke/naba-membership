# Task 7: Schema Migration — Opt-in, Badges, Privacy Controls

## Objective

Add new columns to `DirectoryProfile` for opt-in visibility, badges, bio,
gallery, privacy preferences, and connect settings. Seed the specified
members as opted-in with their assigned badges.

## Schema Changes to `DirectoryProfile`

Add these columns to `api/models.py`:

```python
# Opt-in visibility
opted_in: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
opted_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

# Badges (comma-separated: "staff", "board", "former board")
badges_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)

# Rich profile fields (primarily for business directory)
bio: Mapped[Optional[str]] = mapped_column(String, nullable=True)
logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
gallery_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)
phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
social_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)

# Privacy controls
show_city: Mapped[bool] = mapped_column(Boolean, default=True)
show_member_since: Mapped[bool] = mapped_column(Boolean, default=True)

# Connect/outreach
allow_connect: Mapped[bool] = mapped_column(Boolean, default=False)

# Business-specific
services_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
regions_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

## Update Pydantic Schema (`api/schemas.py`)

Add the new fields to `DirectoryProfilePublic`:

```python
badges: List[str] = []
bio: Optional[str] = None
logo_url: Optional[str] = None
gallery: List[str] = []
phone: Optional[str] = None
social: Optional[dict] = None
allow_connect: bool = False
services: List[str] = []
regions: List[str] = []
member_since_year: Optional[int] = None  # existing, but now conditional
```

Note: `city`, `state_province`, `member_since_year` should be **omitted**
from the response if the member has set `show_city = False` or
`show_member_since = False`. Handle this in the router when building DTOs.

## Update Visibility Logic

In `api/routers_public_members.py`, change the query filter from:

```python
.where(DirectoryProfile.visibility_public.is_(True))
```

to:

```python
.where(
    DirectoryProfile.visibility_public.is_(True),
    DirectoryProfile.opted_in.is_(True),
)
```

## Entry Type for Professional Members

Professional members should **not** be automatically moved to the
business directory. Instead, they keep `entry_type = "individual"` by
default but can **opt in** to appearing in the business directory.

This is handled via the admin editing API (Task 11) or future self-service
editing (Task 12). An admin (or the member themselves) sets
`entry_type = "business"` on their profile.

The sync script's `derive_entry_type()` remains unchanged — sponsors and
vendors are still auto-classified as business. Professional members stay
as individuals unless manually overridden.

## Seed Data

After running the sync script (which will set all members to
`opted_in = False` by default), run a seed script or migration that:

### Opt-in members (use 2026-03-21 as opted_in_at)

| Name | Member ID | Action |
|------|-----------|--------|
| Jean Lotus | 1 | `opted_in = True` |
| David Kaplan | 18 | `opted_in = True` |
| Mark Jensen | 24 | `opted_in = True` |
| Kenny Fallon | 111 | `opted_in = True` |
| Liz Johndrow | 27 | `opted_in = True` |
| Susan Klinker | 158 | `opted_in = True` |
| Lindsey Love | 93 | `opted_in = True` |
| Mateo Clarke | 372 | `opted_in = True` |
| Laura Clarke | 545 | `opted_in = True` |

### Badges

| Name | Member ID | Badge |
|------|-----------|-------|
| Jean Lotus | 1 | `staff` |
| David Kaplan | 18 | `board` |
| Mark Jensen | 24 | `board` |
| Susan Klinker | 158 | `board` |
| Lindsey Love | 93 | `board` |
| Mateo Clarke | 372 | `board` |
| Kluane Gorsuch | 259 | `board` (also set `opted_in = True`) |
| Kenny Fallon | 111 | `former board` |

### Implementation

Create `scripts/seed_enrichment.py`:

```python
"""
One-time seed for opt-in status and badges.

Usage:
    python -m scripts.seed_enrichment
"""
```

This script should:
1. Open the existing SQLite DB
2. For each member above, update their DirectoryProfile with
   `opted_in`, `opted_in_at`, and `badges_csv`
3. Print what it changed
4. Be idempotent (safe to run multiple times)

## Deliverables

- [ ] `api/models.py` updated with new columns
- [ ] `api/schemas.py` updated with new response fields
- [ ] `api/routers_public_members.py` filters on `opted_in = True`
- [ ] `api/routers_public_members.py` respects `show_city` and
  `show_member_since` privacy prefs when building DTOs
- [ ] `scripts/seed_enrichment.py` created and seeds the specified members
- [ ] After running sync + seed, API returns only 10 opted-in members
- [ ] Badges appear in API responses as `["staff"]`, `["board"]`, etc.
- [ ] Professional members remain `entry_type = "individual"` (opt-in
  to business directory via admin or self-service)
