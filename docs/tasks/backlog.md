# Backlog — Deferred Tasks

Items that are planned but not yet scheduled for implementation.

---

## Image Storage Migration

**Context:** The demo uses local filesystem storage for profile logos
and gallery images (`uploads/` directory served by FastAPI). This is not
production-ready.

**Options to evaluate:**

1. **WordPress Media Library** — Upload images via the WP REST API
   (`POST /wp-json/wp/v2/media`). Images are served from the WP host.
   Keeps media centralized with the WP installation. Requires WP API
   write access (Application Password or admin auth).

2. **S3 / Cloudflare R2** — Dedicated object storage. Most scalable.
   Requires an AWS/Cloudflare account and bucket setup. Images served
   via CDN.

3. **Netlify Blobs** — If the Astro frontend deploys to Netlify, blobs
   could work for small-scale storage.

**Recommendation:** WordPress Media Library is the path of least
resistance since WP is already running and the admin already manages
media there. For production scale, migrate to R2/S3.

**Depends on:** Task 9 (business profiles) or Task 11 (admin editing)

---

## Connect Form — Email Notifications

**Context:** Task 10 builds the connect form and admin moderation queue.
When an admin approves a message, the member should be notified.

**Implementation:**

- Use a transactional email service (Resend, Postmark, SendGrid, or
  even WordPress's `wp_mail` via the REST API)
- On approval, send an email to the member with the sender's name and
  message (but NOT the sender's email — the member replies through the
  site or the admin forwards)
- Include an unsubscribe / opt-out link
- Consider digest emails (daily summary of approved messages) vs.
  immediate per-message notifications

**Security:**
- Never expose the member's email to the sender
- Rate limit notification emails per member
- Allow members to disable connect notifications (`allow_connect = False`)

**Depends on:** Task 10 (connect form)

---

## Admin Dedup UI

**Context:** Task 13 builds the detection script. The admin needs a way
to review and resolve duplicates through an interface.

**Implementation:**
- Admin API endpoints for listing duplicate groups and merging records
- Merge preserves enrichment data from the merged record
- Merged records are hidden, not deleted (audit trail)

**Depends on:** Task 13 (dedup detection)

---

## Dedup Reconciliation Rollout (Manual + Staged)

**Context:** Task 13 now includes detection + reconciliation scripts:
`scripts/detect_duplicates.py` and `scripts/reconcile_duplicates.py`.
We need a safe rollout plan for production/staging and a manual review
queue for ambiguous groups.

**Recommended rollout:**
- Run dry-run plan first:
  `python -m scripts.reconcile_duplicates`
- Apply only spam first (lowest risk):
  `python -m scripts.reconcile_duplicates --execute --only-action flag-spam`
- Then apply merges in small batches (e.g. 5 groups):
  `python -m scripts.reconcile_duplicates --execute --only-action merge --max-groups 5`
- Re-run duplicate reports after each batch:
  `python -m scripts.detect_duplicates --format text --output data/duplicate_report.txt`
  and `--format json` for machine-readable diffing

**Manual review workflow (for `suggested_action=review`):**
- Keep a decision log (CSV/JSON) with:
  `display_name`, `keep_id`, `merge_ids`, `decision`, `reviewer`, `date`, `notes`
- Decision options: `merge`, `keep-both`, `flag-spam`, `defer`
- Prioritize high-confidence review groups first (exact name + same domain/location)
- Explicitly verify business+personal pairs before merging

**Operational guardrails:**
- Backup DB before each execute batch
- Never hard-delete records; hide secondary profiles (`visibility_public=False`)
- Keep merged records opted out (`opted_in=False`) unless intentionally restored
- Re-link `connect_messages` to the kept profile ID during merges
- Mirror finalized identity fixes in MemberPress so sync does not reintroduce noise

**Production data source note:**
- Treat MemberPress as source of truth for account identity and membership status
- Treat local API DB as source of truth for directory enrichment fields
- After each local merge decision, reconcile corresponding MemberPress accounts
  (disable/archive obvious duplicate or spam accounts as appropriate)

**Depends on:** Task 13 (dedup detection/reconciliation), Task 8 (sync merge strategy)

---

## Sync-Time Duplicate Detection

**Context:** When the sync script pulls new members from WP, it should
flag potential duplicates rather than silently inserting them.

**Implementation:**
- After fetching from WP, compare new members against existing DB
  records by name + email domain
- Flag matches in a `duplicate_flags` table
- Report flagged duplicates in the sync summary

**Depends on:** Task 8 (merge strategy), Task 13 (dedup)

---

## Email Domain Blocklist for Spam

**Context:** Several accounts use `bylup.com` and similar suspicious
domains. Auto-flagging these during sync would reduce noise.

**Implementation:**
- Maintain a blocklist in the DB or config
- During sync, auto-set `visibility_public = False` for blocked domains
- Log blocked accounts

**Depends on:** Task 8 (merge strategy), Task 13 (dedup)

---

## Member Detail Pages

**Context:** Currently only business listings get full detail pages
(Task 9). Individual member entries are card-only.

**Future:** If members want richer profiles (bio, links), add individual
detail pages at `/directory/member/:id`. Keep them simpler than
business pages — no gallery, just bio + links + badges.

**Depends on:** Task 9 (business profiles — reuse layout components)

---

## Connect Form — Board Validation

**Context:** The board liked the "Connect" form concept during the
March 2026 demo. Members opt in to receiving outreach via the site,
and submissions are moderated before delivery.

**Status:** Core connect form and moderation queue are implemented
(Task 10). Remaining work is email delivery on approval (see above)
and member-facing notification preferences.

---

## Directory Filters by Material & Category

**Context:** Task 14 adds categories and materials to profiles. Once
data is populated, add filter UI to the directory page — clickable
material chips and category toggles that filter the visible cards.

**Depends on:** Task 14 (categories & materials)

---

## Map–Directory Filter Sync

**Context:** Task 15 enhances the map. A stretch goal is syncing
filters between the map and directory pages — e.g., selecting "Straw
Bale" on the directory also filters map markers, and clicking a state
on the map filters the directory.

**Depends on:** Task 14 (filters), Task 15 (interactive map)
