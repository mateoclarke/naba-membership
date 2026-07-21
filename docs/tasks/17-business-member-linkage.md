# Task 17: Business–Member Linkage

## Objective

Model the relationship between individual members and the businesses
they represent, so that a person can manage a business profile and a
business can show its team members.

## Background

The current data has inconsistencies:
- Some memberships are under a business name (e.g., "Love Schack
  Architecture") but represent an individual.
- Some individuals have separate personal and business accounts
  (e.g., Anthony Dente + admin@verdantstructural.com).
- Sponsors may have multiple contacts (e.g., Hempitecture has both
  Thomas Gibbons and Mattie Mead).

We need a way to say "this person manages this business profile" and
"this business has these team members."

---

## Data Model

### New table: `business_members`

A many-to-many join table linking `DirectoryProfile` (business) to
`DirectoryProfile` (individual member).

```python
class BusinessMember(Base):
    __tablename__ = "business_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_profile_id: Mapped[int] = mapped_column(Integer, index=True)
    member_profile_id: Mapped[int] = mapped_column(Integer, index=True)
    role_in_business: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime)
```

- `business_profile_id` → `directory_profiles.id` where
  `entry_type = 'business'`
- `member_profile_id` → `directory_profiles.id` where
  `entry_type = 'individual'`
- `role_in_business` — free text like "Owner", "Sales", "Architect"
- `can_edit` — if True, this member can edit the business profile
  when logged in (self-service)

### Usage examples

| Business             | Member           | Role    | Can Edit |
|----------------------|------------------|---------|----------|
| Verdant Structural   | Anthony Dente    | Owner   | ✓        |
| Verdant Structural   | Clare Wolfe      | Partner | ✓        |
| Hempitecture         | Thomas Gibbons   | —       | ✓        |
| Hempitecture         | Mattie Mead      | —       | ✓        |
| Thruline Partners    | Lotus Grenier    | Owner   | ✓        |

---

## API Changes

### Public

- `GET /api/v1/public/members/{id}` — for business profiles, include
  a `team` array listing linked members (name, role_in_business).
- `GET /api/v1/public/members/{id}` — for individual profiles, include
  an `affiliated_businesses` array.

### Self-service

- `GET /api/v1/me/businesses` — list businesses the logged-in member
  can edit.
- `PUT /api/v1/me/businesses/{business_id}/profile` — edit a linked
  business profile (same scope as `/me/profile` but targeting the
  business).

### Admin

- `POST /api/v1/admin/business-members` — link a member to a business.
- `DELETE /api/v1/admin/business-members/{id}` — remove a link.
- `GET /api/v1/admin/business-members?business_id=...` — list links.

---

## UI Changes

### Business detail page

- Show a "Team" section listing linked members with their roles.

### Profile editor

- If a logged-in member has `can_edit` links, show a "Your businesses"
  section listing their linked businesses with "Edit" buttons.
- Editing a business profile uses the same form as the personal profile
  editor but targets the business profile.

### Admin tooling

- Admin can link/unlink members and businesses.
- Eventually, a drag-and-drop or search UI.

---

## Handling Sponsor Inconsistencies

### Pattern: Membership is under business name

Example: "Love Schack Architecture" (ID 428) is a WP membership under
the business name, not a person.

**Resolution:**
1. Convert the profile to `entry_type = "business"`.
2. If we know the individual contact (Paula), create or find their
   personal profile and link it via `business_members`.

### Pattern: Individual has personal + business accounts

Example: Anthony Dente has IDs 162 (personal) and 574 (business admin).

**Resolution:**
1. Keep ID 162 as the individual profile.
2. Create or convert a business profile for Verdant Structural.
3. Link ID 162 → Verdant Structural via `business_members`.
4. Flag ID 574 as a duplicate (Task 13).

### Pattern: Sponsor has multiple contacts

Example: Hempitecture has Thomas Gibbons (ID 599) and Mattie Mead.

**Resolution:**
1. Create one Hempitecture business profile.
2. Link both contacts to it via `business_members`.
3. Both get `can_edit = True`.

---

## Deliverables

- [ ] Create `BusinessMember` model and migration
- [ ] Admin API endpoints for managing links
- [ ] Public API: include team/affiliated data in profile responses
- [ ] Self-service: let linked members edit business profiles
- [ ] UI: "Team" section on business detail pages
- [ ] UI: "Your businesses" section in profile editor
- [ ] Seed initial links for known sponsors (from Task 16 data)
