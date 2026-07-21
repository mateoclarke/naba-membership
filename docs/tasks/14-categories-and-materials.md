# Task 14: Member Categories & Materials Taxonomy

## Objective

Add two new structured taxonomies to member profiles so that directory
users can identify **what a member does** (category) and **what
materials they work with**.

## Background

The board wants more visual, icon-driven badges that go beyond
staff/board roles. Members should be able to self-identify across two
dimensions:

1. **Category** — their professional orientation
2. **Materials** — the natural building materials they have experience
   or interest in

These are multi-select: a member can be both a "Professional" and an
"Educator," and can list multiple materials.

---

## 1. Categories

Proposed categories (multi-select, displayed as badges on cards):

| Category      | Description                                          | Example Members        |
|---------------|------------------------------------------------------|------------------------|
| Professional  | Contractor, tradesperson, architect, engineer, etc.  | Anthony Dente, Tyler Survant |
| Owner/Builder | Homeowner who built or is building their own home    | Laura Clarke           |
| Vendor        | Offers or represents a product                       | Faswall, Hempitecture  |
| Educator      | Teaches workshops, university courses, or training   | Tyler Survant (MSU)    |

### Visual treatment

- Each category gets a distinct **icon + color** badge (similar to
  staff/board badges but richer).
- Suggested icons (Unicode or inline SVG):
  - Professional: 🔧 or 🏗️
  - Owner/Builder: 🏠
  - Vendor: 📦
  - Educator: 🎓
- Badges render as small pills: `🔧 Professional`, `🎓 Educator`
- Consider using an icon library like Lucide Icons for the icons and have the ability to create/generate SVG in the style of the library. 

### Data model

Add a new column to `DirectoryProfile`:

```python
categories_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

Values stored as comma-separated lowercase strings:
`professional,educator`

This follows the same pattern as `badges_csv`, `services_csv`, etc.

### API changes

- Add `categories: List[str]` to `DirectoryProfileListItem` and
  `DirectoryProfilePublic` schemas (parsed from `categories_csv`).
- Add `categories_csv` to `ProfileAdminDetail` and `ProfileSelfUpdate`
  so members can set their own categories.

---

## 2. Materials

A predefined set of natural building materials. Members select which
ones they have experience or interest in.

### Initial material list

1. Adobe
2. Compressed Earth Block (CEB)
3. Rammed Earth
4. Cob
5. Light Straw Clay
6. Hempcrete
7. Timber Framing
8. Straw Bale
9. Natural Plaster
10. _(Other — free text, future consideration)_

### Visual treatment

- Displayed as colored chips/tags on member cards (similar to existing
  tags but with a distinct "materials" color palette — earthy tones).
- On the directory page, materials can also serve as **filter chips**
  so visitors can find members by material.

### Data model

Add a new column to `DirectoryProfile`:

```python
materials_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

Values stored as comma-separated lowercase:
`adobe,rammed earth,straw bale`

### API changes

- Add `materials: List[str]` to the list and public schemas.
- Add `materials_csv` to `ProfileAdminDetail` and `ProfileSelfUpdate`.

---

## 3. UI Updates

### Directory cards

- Render category badges below the name (with icon + label).
- Render material chips in a "Materials" row using earthy-toned pills.
- Both visible in the default public view and the admin "show all" view.

### Profile editor (`/account/profile`)

- Add a **Categories** section with checkboxes for the four categories.
- Add a **Materials** section with checkboxes for the predefined list.

### Directory filters

- Add a "Filter by material" row of clickable chips above the card
  grid. Clicking a material filters the visible cards client-side.
- Consider adding category filters as well.

---

## 4. Sync considerations

- `categories_csv` and `materials_csv` are enrichment fields — they
  are **not** overwritten by the WP sync. Same treatment as `bio`,
  `badges_csv`, etc.
- The `_PROFILE_WP_FIELDS` list in `sync_from_wordpress.py` should
  **not** include these new columns.

---

## Deliverables

- [x] Schema migration: add `categories_csv` and `materials_csv` columns
- [x] Update Pydantic schemas (list item, public, admin, self-update)
- [x] Update `_profile_to_list_item` and `_profile_to_detail` to parse
      new CSV fields
- [x] Update `ProfileSelfUpdate` to include new fields
- [x] Update directory card rendering (SSR + client-side `cardHtml`)
- [x] Add category/material icons and colors
- [x] Update profile editor with checkboxes
- [x] Add material filter chips to directory page
- [x] Seed some demo data (categories + materials for opted-in members)

---

## Current implementation status (Mar 2026)

This task is not yet implemented in code. The existing codebase currently has:

- CSV enrichment fields for badges/services/regions/tags, but no
  `categories_csv` or `materials_csv`.
- Public/admin/self profile schemas and transformers that parse
  `tags/badges/services/regions`, but not categories/materials.
- Directory card UI and profile editor UI without category/material inputs
  or rendering.
- No DB migration helper for these two columns yet.

---

## Implementation plan (file-level)

### Backend data model and DB bootstrap

1. Update `api/models.py`:
   - Add:
     - `categories_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)`
     - `materials_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)`
2. Update `api/db.py`:
   - Add SQLite safe migration helpers similar to slug:
     - `ensure_directory_profile_categories_column(...)`
     - `ensure_directory_profile_materials_column(...)`
   - Call both during app startup initialization path.
3. Update API docs in `api/README.md` for new fields.

### Backend schemas and serializers

1. Update `api/schemas.py`:
   - Add `categories: List[str] = []` and `materials: List[str] = []` to:
     - `DirectoryProfileListItem`
     - `DirectoryProfilePublic`
   - Add raw CSV fields to:
     - `ProfileAdminDetail`: `categories_csv`, `materials_csv`
     - `ProfileSelfUpdate`: `categories_csv`, `materials_csv`
     - `ProfileAdminUpdate`: `categories_csv`, `materials_csv` (for admin parity)
2. Update `api/routers_public_members.py`:
   - Parse both CSV fields in:
     - `_profile_to_list_item`
     - `_profile_to_detail`
3. Update `api/routers_admin.py`:
   - Include raw CSV fields in `_profile_to_admin_detail(...)`.
4. `api/routers_me.py` already uses model-dump passthrough update; once
   schema fields are added, self-service writes will work.

### Frontend directory and profile editor

1. Update `astro-app/src/pages/directory.astro`:
   - Extend `DirectoryEntry` + API mapper with:
     - `categories: string[]`
     - `materials: string[]`
   - Render category pills with icon + label.
   - Render materials chips row on cards.
   - Update client-side `cardHtml(...)` rendering to match SSR output.
2. Add category style map:
   - professional, owner/builder, vendor, educator
   - include consistent icon and colors for SSR + client JS.
3. Add material filter chips:
   - UI control above cards
   - client-side filter state + active chip styling
   - only affects currently selected view (members/businesses) or both,
     choose and document behavior.
4. Update `astro-app/src/components/MemberProfileEditor.tsx`:
   - Replace free-text categories/materials entry with checkbox groups.
   - Persist values as normalized CSV strings to `PUT /api/v1/me/profile`.

### Seed/demo data

1. Update seeding script (`scripts/seed_members_from_csv.py` or dedicated
   enrichment script) to set sample categories/materials for opted-in users.
2. Regenerate `astro-app/public/data/directoryEntries.json` if static demo
   data should include new fields.

---

## Suggested acceptance tests

- `GET /api/v1/public/members/` returns `categories` and `materials` arrays.
- `GET /api/v1/public/members/{id}` and `/by-slug/{slug}` include both arrays.
- `GET /api/v1/admin/profiles/{id}` includes `categories_csv` and
  `materials_csv`.
- `PUT /api/v1/me/profile` accepts and persists `categories_csv` and
  `materials_csv`.
- Directory cards show category icon badges and materials chips in SSR and
  after client API hydration.
- Material filter chips correctly narrow visible cards and can be cleared.
- Existing WP sync does not overwrite either new enrichment column.
