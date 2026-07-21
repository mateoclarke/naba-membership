# Task 11: Admin Profile Editing API

## Objective

Build CRUD API endpoints for admins to manage directory profiles:
update badges, bio, gallery, opt-in status, privacy settings, and
entry type. For now, admin auth is a simple API key; WP-based auth
comes in Task 12.

## Authentication (interim)

Add an `ADMIN_API_KEY` to `.env.schema` and `api/config.py`:

```env-spec
# @type=string @sensitive
ADMIN_API_KEY=
```

Admin endpoints check for this key in the `Authorization` header:

```
Authorization: Bearer <ADMIN_API_KEY>
```

This is a stopgap. Task 12 replaces it with WP-based auth.

## API Endpoints

### List all profiles (admin view — includes hidden members)

```
GET /api/v1/admin/profiles
```

Query params: `page`, `page_size`, `q`, `opted_in` (bool filter)

Returns all profiles regardless of visibility/opt-in status. Includes
enrichment fields not shown in the public API.

### Get single profile (admin detail)

```
GET /api/v1/admin/profiles/:id
```

Returns full profile including internal fields.

### Update profile

```
PUT /api/v1/admin/profiles/:id
```

Request body (all fields optional — only provided fields are updated):

```json
{
  "opted_in": true,
  "badges_csv": "board",
  "bio": "Natural building educator and consultant.",
  "entry_type": "business",
  "organization": "Clarke Natural Building",
  "show_city": true,
  "show_member_since": true,
  "allow_connect": true,
  "website_url": "https://example.com",
  "phone": "555-0123",
  "social_json": "{\"instagram\": \"@clarkenbuild\"}",
  "services_csv": "consulting, workshops, design",
  "regions_csv": "New Mexico, Southwest US",
  "tags_csv": "board, earthen plaster, straw bale"
}
```

### Upload logo

```
POST /api/v1/admin/profiles/:id/logo
```

Multipart file upload. Saves to `uploads/profiles/{id}/logo.{ext}`.
Updates `logo_url` in the DB.

### Upload gallery images

```
POST /api/v1/admin/profiles/:id/gallery
```

Multipart file upload (one or more files). Appends to
`gallery_json` array in the DB.

### Delete gallery image

```
DELETE /api/v1/admin/profiles/:id/gallery/:index
```

Removes the image at the given index from `gallery_json` and deletes
the file from disk.

## Pydantic Schemas

```python
class ProfileAdminUpdate(BaseModel):
    opted_in: Optional[bool] = None
    badges_csv: Optional[str] = None
    bio: Optional[str] = None
    entry_type: Optional[str] = None
    organization: Optional[str] = None
    show_city: Optional[bool] = None
    show_member_since: Optional[bool] = None
    allow_connect: Optional[bool] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    social_json: Optional[str] = None
    services_csv: Optional[str] = None
    regions_csv: Optional[str] = None
    tags_csv: Optional[str] = None

class ProfileAdminDetail(DirectoryProfilePublic):
    email: Optional[str] = None  # from Member table
    opted_in: bool
    opted_in_at: Optional[str] = None
    badges_csv: Optional[str] = None
    show_city: bool
    show_member_since: bool
    allow_connect: bool
    phone: Optional[str] = None
    social_json: Optional[str] = None
    services_csv: Optional[str] = None
    regions_csv: Optional[str] = None
```

## Router

Create `api/routers_admin.py` mounted under `/api/v1/admin`.

## Deliverables

- [ ] `ADMIN_API_KEY` added to `.env.schema`
- [ ] `api/routers_admin.py` with all CRUD endpoints
- [ ] Admin auth middleware (API key check)
- [ ] Profile update endpoint (partial updates)
- [ ] Logo upload endpoint
- [ ] Gallery upload/delete endpoints
- [ ] Admin list view includes hidden/non-opted-in members
- [ ] All endpoints tested via curl
