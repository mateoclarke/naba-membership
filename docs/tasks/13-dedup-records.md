# Task 13: Detect and Manage Duplicate / Similar Records

## Objective

Build tooling to identify, flag, and resolve duplicate or near-duplicate
member records. The WordPress/MemberPress data contains members who
registered multiple times with different email addresses or accounts.

## Current State

Analysis of the 578 synced members found:

- **536 unique display names** (35 name collisions across 42 extra records)
- **0 duplicate emails** (each account has a distinct email)
- Duplicates fall into several categories (see below)

## Duplicate Categories

### 1. Same person, multiple accounts (most common)

Members who signed up more than once with different emails. One account
is usually active, the others expired or inactive.

Examples:
- **Jean Lotus** (IDs 1, 432) — org email + personal email, both active
- **Lindsey Love** (IDs 93, 257, 433) — 3 accounts, 1 active
- **Ryan Chivers** (IDs 51, 354, 466, 582) — 4 accounts across
  different businesses

### 2. Business + personal accounts

Members who have a personal membership and a separate business account.

Examples:
- **Anthony Dente** (IDs 162, 574) — personal + admin@verdantstructural
- **Clare Wolfe** (IDs 374, 484) — personal + clare@verdantstructural

These might be intentional (person + business both listed).

### 3. Likely spam or test accounts

Multiple accounts from the same name with suspicious email domains or
patterns.

Examples:
- **ricardo martinez** (IDs 306, 307, 310) — all `bylup.com` emails
- **jose diaz** (IDs 223, 227, 230) — mix of real + `bylup.com`
- **Heliom Meses** (IDs 236, 249) — near-identical emails

### 4. Legitimate same-name, different people

Less likely at NaBA's scale but possible. Would need email or location
to distinguish.

## Approach

### Phase 1: Detection script (immediate)

Create `scripts/detect_duplicates.py` that identifies potential
duplicates using multiple signals:

**Name matching:**
- Exact display_name match (case-insensitive)
- Fuzzy match (Levenshtein distance ≤ 2, or normalized similarity > 0.85)

**Email domain matching:**
- Same email domain (e.g. `@verdantstructural.com`) across different
  member IDs

**Location matching:**
- Same city + state for name matches (strengthens confidence)

**Output:** A report (stdout or JSON) listing duplicate groups with:
- Member IDs, names, emails, status, location
- Confidence level: high (exact name + same domain or location),
  medium (exact name), low (fuzzy name match)
- Suggested action: merge, keep-both, flag-spam

### Phase 2: Admin dedup UI / API (later)

Admin endpoints to:

```
GET /api/v1/admin/duplicates
```

Returns duplicate groups with confidence scores.

```
POST /api/v1/admin/duplicates/merge
Body: {
  "keep_id": 432,
  "merge_ids": [1],
  "strategy": "keep_newest_active"
}
```

Merge strategy:
- Keep the designated primary record
- Transfer any enrichment data (badges, bio, gallery) from merged
  records to the primary
- Mark merged records as hidden (`visibility_public = False`)
- Do **not** delete records — keep them for audit trail
- Update `member_id` references in `connect_messages` table

### Phase 3: Ongoing dedup in sync

Add duplicate detection to the sync script (Task 8) so that when new
WP members come in, potential duplicates are flagged rather than
silently added. The sync summary should report:

```
  Possible duplicates found:  3
```

And write them to a log or a `duplicate_flags` table for admin review.

## Spam Account Handling

For accounts that are clearly spam (e.g., the `bylup.com` cluster):

1. Mark all as `visibility_public = False` and `opted_in = False`
2. Add to a blocklist (email domain or pattern)
3. Future: auto-flag during sync if email matches blocklist

## Data Model

Consider adding a lightweight tracking table:

```python
class DuplicateFlag(Base):
    __tablename__ = "duplicate_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    member_id_a: Mapped[int] = mapped_column(Integer, index=True)
    member_id_b: Mapped[int] = mapped_column(Integer, index=True)
    confidence: Mapped[str] = mapped_column(String)  # high, medium, low
    reason: Mapped[str] = mapped_column(String)       # "exact_name", "fuzzy_name", "same_domain"
    status: Mapped[str] = mapped_column(String, default="unreviewed")  # unreviewed, merged, kept_both, spam
    created_at: Mapped[datetime] = mapped_column(DateTime)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

## Deliverables

### Immediate (this task)

- [x] `scripts/detect_duplicates.py` — detection report script
- [x] Report output generated (`data/duplicate_report.txt`, `data/duplicate_report.json`)
- [x] Spam accounts identified and documented

Run:

```bash
python -m scripts.detect_duplicates --format text --output data/duplicate_report.txt
python -m scripts.detect_duplicates --format json --output data/duplicate_report.json
```

Current output snapshot (Mar 2026 data):

- Exact duplicate groups: 38
- Records in exact duplicate groups: 83
- Fuzzy name pairs: 5
- Spam-flagged accounts: 14

Note: this run finds 38 exact-name duplicate groups (not 35), likely due to
additional synced records since the initial analysis.

Spam cluster (domain heuristic: `bylup.com`) includes member IDs:
218, 219, 225, 226, 227, 230, 231, 235, 243, 306, 307, 310, 311, 312.

### Later (backlog)

- [ ] Admin API for duplicate review and merge
- [ ] Merge logic that preserves enrichment data
- [ ] Sync-time duplicate detection
- [ ] Email domain blocklist

## Known Duplicate Groups (from current data)

| Name | IDs | Pattern | Suggested Action |
|------|-----|---------|-----------------|
| Jean Lotus | 1, 432 | Org + personal email | Admin decides primary |
| Lindsey Love | 93, 257, 433 | 3 accounts | Keep 257 (active) |
| Ryan Chivers | 51, 354, 466, 582 | 4 accounts, 2 active | Admin decides |
| Cheryl Corsiglia | 150, 151, 572 | 3 accounts | Keep 572 (active) |
| daniel campos | 239, 332, 335 | 3 accounts, suspicious | Review |
| ricardo martinez | 306, 307, 310 | All bylup.com | Spam — hide all |
| jose diaz | 223, 227, 230 | Mix real + bylup | Spam — hide all |
| Heliom Meses | 236, 249 | Near-identical emails | Spam — hide all |
| Anthony Dente | 162, 574 | Personal + business | Maybe keep both |
| David Rosprim | 475, 584 | 2 active accounts | Admin decides |
