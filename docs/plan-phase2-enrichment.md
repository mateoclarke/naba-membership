# Plan: Phase 2 — Directory Enrichment, Opt-in, Connect

## Overview

Phase 1 established the pipeline: WordPress → sync → SQLite → FastAPI →
Astro. Phase 2 adds:

1. **Opt-in visibility** — members hidden by default, must explicitly opt
   in before appearing in the directory
2. **Badges & roles** — staff, board, former board, etc.
3. **Professional → Business directory** — professional members appear as
   business listings
4. **Rich business profiles** — logo, gallery, bio, phone, social links,
   individual detail pages (inspired by
   [Urban Wood Network](https://urbanwoodnetwork.org/listing/denver-wood-slabs/))
5. **Connect/outreach form** — visitors can message members through the
   site, with moderation to protect against spam/abuse
6. **Admin profile editing** — CRUD API for managing profiles
7. **Self-service editing & auth** — members edit their own profiles via
   WP-based authentication (future)

## Architecture Decision: Two-Layer Data Model

**WordPress/MemberPress** remains the authority for:
- Membership status, billing, payments
- Basic identity (name, email, address)
- Login credentials

**FastAPI/SQLite** owns the enrichment layer:
- Opt-in status and date
- Badges (staff, board, etc.)
- Bio, gallery, logo
- Privacy preferences (show/hide city, member_since)
- Connect form preferences and message queue
- Entry type overrides (professional → business)

**Sync strategy changes from wipe-and-replace to merge:**
- WP-sourced fields (name, address, membership status) are updated
- Local enrichment fields are preserved across syncs
- New WP members get a profile row with defaults (hidden, no badges)
- Deleted WP members are marked hidden (not removed)

## Schema Changes

### DirectoryProfile — new columns

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `opted_in` | bool | `False` | Must be True to appear in directory |
| `opted_in_at` | datetime | null | When the member opted in |
| `badges_csv` | string | null | Comma-separated: "staff", "board", "former board" |
| `bio` | text | null | Short description / about text |
| `logo_url` | string | null | Business logo (path or URL) |
| `gallery_json` | text | null | JSON array of image paths/URLs |
| `phone` | string | null | Business phone (opt-in display) |
| `social_json` | text | null | JSON: {"facebook": "...", "instagram": "..."} |
| `show_city` | bool | `True` | Member can hide city from directory |
| `show_member_since` | bool | `True` | Member can hide member_since_year |
| `allow_connect` | bool | `False` | Member accepts outreach via site |
| `services_csv` | string | null | For business listings: services offered |
| `regions_csv` | string | null | Regions served |

### New table: ConnectMessage

| Column | Type | Purpose |
|--------|------|---------|
| `id` | int PK | Auto-increment |
| `recipient_profile_id` | int FK | Who is being contacted |
| `sender_name` | string | From the form |
| `sender_email` | string | From the form |
| `message_body` | text | The message |
| `status` | string | "pending", "approved", "rejected", "spam" |
| `created_at` | datetime | Submission time |
| `reviewed_at` | datetime | When admin acted |
| `ip_address` | string | For rate limiting / abuse detection |
| `honeypot_value` | string | Honeypot field value (should be empty) |

### Visibility logic changes

Current: `visibility_public = True` if member is active.

New: A profile is visible in the public directory only if **all** of:
1. `visibility_public = True` (active membership)
2. `opted_in = True`

The public API filters on both conditions.

## Decisions Made

1. **Data ownership:** Our FastAPI/SQLite DB owns enrichment data. WP
   owns membership/billing. Sync is merge-based (preserves enrichment).
   No write-back to WP.
2. **Professional → Business:** Professional members are NOT auto-moved
   to the business directory. They keep `entry_type = "individual"` and
   can opt in to the business directory via admin or self-service.
3. **Image storage:** Local filesystem for demo. Backlogged: migrate to
   WordPress Media Library or S3/R2 for production.
4. **Connect form notifications:** Messages stored + moderated. Email
   notification to members on approval is backlogged.
5. **Detail pages:** Business listings get full detail pages. Individual
   member entries stay as cards only (for now).

## Task Breakdown

| # | Task | File | Status |
|---|------|------|--------|
| 7 | Schema migration + opt-in + seed data | `docs/tasks/07-schema-optin-badges.md` | Ready |
| 8 | Sync script merge strategy | `docs/tasks/08-sync-merge-strategy.md` | Ready |
| 9 | Rich business profiles + detail pages | `docs/tasks/09-business-profiles.md` | Ready |
| 10 | Connect form + moderation | `docs/tasks/10-connect-form.md` | Ready |
| 11 | Admin profile editing API | `docs/tasks/11-admin-editing.md` | Ready |
| 12 | Auth + self-service editing | `docs/tasks/12-auth-self-service.md` | Future |
| 13 | Duplicate record detection + management | `docs/tasks/13-dedup-records.md` | Ready |

Backlogged items are tracked in `docs/tasks/backlog.md`.

## Security Considerations (Connect Form)

- **Rate limiting:** Max N submissions per IP per hour
- **Honeypot field:** Hidden form field; if filled, mark as spam
- **Content filtering:** Block messages with suspicious URLs, excessive
  links, or known spam patterns
- **Email validation:** Basic format check on sender email
- **No direct email forwarding:** Messages are stored and reviewed; the
  member's email is never exposed to the sender
- **Admin moderation queue:** All messages start as "pending" and must be
  approved before any notification goes to the member
- **CSRF protection:** Form includes a token to prevent cross-site
  submission
