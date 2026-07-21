# Task 9: Rich Business Directory Profiles + Detail Pages

## Objective

Build individual detail pages for business/professional directory
listings with rich content: bio, logo, gallery, contact info, social
links, and services. Inspired by
[Urban Wood Network](https://urbanwoodnetwork.org/listing/denver-wood-slabs/).

## Reference: Urban Wood Network Listing

Key elements from the UWN listing:

- **Header:** Business name, chapter/region subtitle
- **Category badges:** (wood producer, kiln service, etc.)
- **Description:** Full paragraph bio
- **Contact actions:** Send Email, Visit Website, Call (buttons)
- **Social links:** Facebook, Instagram icons
- **Gallery:** Grid of photos with lightbox

## NaBA Adaptation

### Business Directory Detail Page

Route: `/directory/business/:id` or `/directory/business/:slug`

Layout:

```
┌──────────────────────────────────────────────┐
│  [Logo]  Business Name                       │
│          Location  •  Member since 2019      │
│          ┌──────┐ ┌──────┐ ┌──────┐          │
│          │ tag  │ │ tag  │ │ tag  │          │
│          └──────┘ └──────┘ └──────┘          │
├──────────────────────────────────────────────┤
│  Bio / description paragraph(s)              │
│                                              │
├──────────────────────────────────────────────┤
│  ┌────────┐  ┌─────────────┐  ┌──────┐      │
│  │Website │  │ Connect     │  │ Call │      │
│  └────────┘  └─────────────┘  └──────┘      │
│  [Facebook] [Instagram]                      │
├──────────────────────────────────────────────┤
│  Services: design, consulting, workshops     │
│  Regions: Colorado, Southwest US             │
├──────────────────────────────────────────────┤
│  Gallery                                     │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐           │
│  │ img │ │ img │ │ img │ │ img │           │
│  └─────┘ └─────┘ └─────┘ └─────┘           │
└──────────────────────────────────────────────┘
```

### Member Directory Cards

For individual members, the existing card format is sufficient. No
detail pages needed for now. Cards show:
- Name
- Role badge (staff, board)
- Location (if `show_city = True`)
- Member since (if `show_member_since = True`)
- Tags

### API Changes

Add a detail endpoint:

```
GET /api/v1/public/members/:id
```

Returns the full `DirectoryProfilePublic` for a single opted-in member,
including fields not shown in the list view:
- `bio`
- `logo_url`
- `gallery` (parsed from `gallery_json`)
- `phone`
- `social` (parsed from `social_json`)
- `services` (parsed from `services_csv`)
- `regions` (parsed from `regions_csv`)

### Image Handling

For the demo, images are served from the local filesystem:

```
uploads/
  profiles/
    {member_id}/
      logo.png
      gallery/
        001.jpg
        002.jpg
```

FastAPI serves these via `StaticFiles`:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
```

URLs stored in the DB as relative paths: `/uploads/profiles/372/logo.png`

Future: migrate to S3/R2 and store full URLs.

### Astro Detail Page

Create `astro-app/src/pages/directory/business/[id].astro` (or similar)
that:
1. Fetches the profile from `GET /api/v1/public/members/:id`
2. Renders the full detail layout
3. Includes the Connect form if `allow_connect = True`

### Image Upload Endpoint (Admin)

```
POST /api/v1/admin/profiles/:id/logo
POST /api/v1/admin/profiles/:id/gallery
```

Accept multipart file uploads, save to the filesystem, update the DB.
Admin auth required (API key or basic auth for now).

## Deliverables

- [ ] `GET /api/v1/public/members/:id` detail endpoint
- [ ] Detail page response includes bio, gallery, social, services
- [ ] Astro business detail page template
- [ ] Image upload endpoints (admin)
- [ ] Static file serving for uploaded images
- [ ] Business card in directory links to detail page
- [ ] Gallery renders as a grid on the detail page
