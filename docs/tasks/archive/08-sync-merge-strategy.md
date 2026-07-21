# Task 8: Sync Script — Merge Strategy (Preserve Enrichment)

## Objective

Refactor `scripts/sync_from_wordpress.py` to use a **merge/upsert**
strategy instead of wipe-and-replace. WP-sourced fields (name, address,
membership status) are updated, but locally-managed enrichment fields
(badges, bio, gallery, opt-in, privacy prefs) are preserved.

## Problem

The current sync does:

```python
db.execute(delete(DirectoryProfile))
db.execute(delete(Member))
```

This destroys any enrichment data (badges, bio, opt-in) that was added
after the initial sync. Every re-sync would reset all profiles.

## Solution

Change to a merge strategy:

```
For each WP member:
  1. Check if Member row exists (by id)
     - If yes: UPDATE wp-sourced fields only
     - If no: INSERT new Member row
  2. Check if DirectoryProfile row exists (by member_id)
     - If yes: UPDATE wp-sourced fields, PRESERVE enrichment fields
     - If no: INSERT new profile with defaults (opted_in=False, etc.)
  3. Members in SQLite but NOT in WP: mark visibility_public=False
     (don't delete — preserve their enrichment data)
```

### WP-sourced fields (updated on every sync)

**Member table:**
- `first_name`, `last_name`, `email`
- `status`, `memberships_raw`
- `registered_at`, `first_txn_at`, `latest_txn_at`
- `city`, `state_province`, `country`

**DirectoryProfile table:**
- `display_name` (derived from WP name)
- `entry_type` (derived from membership titles)
- `role` (derived from membership title)
- `city`, `state_province`, `country`, `location_display`
- `member_since_year`
- `visibility_public` (derived from membership status)

### Enrichment fields (preserved across syncs)

- `opted_in`, `opted_in_at`
- `badges_csv`
- `bio`
- `logo_url`, `gallery_json`
- `phone`, `social_json`
- `show_city`, `show_member_since`
- `allow_connect`
- `organization` (can be overridden locally)
- `website_url` (can be overridden locally)
- `tags_csv` (merge WP-derived + locally-added tags)
- `services_csv`, `regions_csv`

### Implementation sketch

```python
def upsert_member(db, data):
    wp_id = data["id"]
    existing = db.get(Member, wp_id)
    mapped = map_member(data)

    if existing:
        # Update only WP-sourced fields
        existing.first_name = mapped.first_name
        existing.last_name = mapped.last_name
        existing.email = mapped.email
        existing.status = mapped.status
        existing.memberships_raw = mapped.memberships_raw
        # ... etc
    else:
        db.add(mapped)

    return existing or mapped


def upsert_profile(db, data, member):
    existing = db.query(DirectoryProfile).filter_by(member_id=member.id).first()
    mapped = map_profile(data, member)

    if existing:
        # Update WP-sourced fields
        existing.display_name = mapped.display_name
        existing.entry_type = mapped.entry_type
        existing.role = mapped.role
        existing.city = mapped.city
        # ... etc
        existing.visibility_public = mapped.visibility_public
        # DO NOT touch: opted_in, badges_csv, bio, gallery_json, etc.
    else:
        # New member — insert with all defaults (opted_in=False)
        db.add(mapped)
```

### Handle removed members

```python
# After processing all WP members, find profiles not in WP
wp_ids = {d["id"] for d in all_members}
orphans = db.query(DirectoryProfile).filter(
    ~DirectoryProfile.member_id.in_(wp_ids)
).all()
for orphan in orphans:
    orphan.visibility_public = False
```

## Edge Cases

- **Member re-activates:** If a member was expired and becomes active
  again, `visibility_public` flips back to True. Their enrichment data
  (badges, bio) is still there.
- **Name change in WP:** The sync updates `display_name`. If an admin
  manually set a different display name locally, the WP name will
  overwrite it. Consider adding an `override_display_name` field if
  this becomes an issue.
- **Conflicting tags:** The sync derives tags from membership type.
  Locally-added tags (via admin) should be kept. Strategy: store
  WP-derived tags and local tags separately, or merge carefully.

## Deliverables

- [ ] `scripts/sync_from_wordpress.py` refactored to use merge/upsert
- [ ] Enrichment fields survive re-sync (run sync, add badges, re-sync,
  verify badges still present)
- [ ] New WP members get profile rows with safe defaults
- [ ] Removed/expired WP members are hidden, not deleted
- [ ] Summary output distinguishes created vs updated vs unchanged
