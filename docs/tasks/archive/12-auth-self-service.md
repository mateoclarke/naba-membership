# Task 12: WordPress Auth + Self-Service Profile Editing (Future)

## Objective

Enable NaBA members to sign in using their WordPress/MemberPress
credentials and edit their own directory profiles. This is a future task
that builds on Tasks 7–11.

## Authentication Strategy

### Option A: WordPress Application Passwords (simplest)

WordPress 5.6+ supports Application Passwords. A member can generate
one in their WP profile. Our API validates it against the WP REST API:

```
POST /api/v1/auth/login
Body: { "username": "...", "password": "..." }
```

The API server calls:

```
GET https://wp-site.com/wp-json/wp/v2/users/me
Authorization: Basic base64(username:app_password)
```

If WP returns 200, the user is authenticated. Our API issues a
session token (JWT or similar) for subsequent requests.

**Pros:** No plugins needed on WP side, standard HTTP Basic auth.
**Cons:** Members need to generate an application password in WP.

### Option B: JWT via WP plugin ✅ (IMPLEMENTED)

We use the **Simple JWT Login** plugin (free, no SSH/wp-config.php
changes needed — fully configurable from wp-admin):

```
POST https://wp-site.com/wp-json/simple-jwt-login/v1/auth
Body: { "login": "email-or-username", "password": "..." }
→ { "success": true, "data": { "jwt": "..." } }
```

Our FastAPI validates the token by calling `/wp/v2/users/me` with it,
extracts the WordPress user ID, and issues a NaBA session JWT.

**Pros:** Best UX (uses regular WP password), no SSH required.
**Cons:** Requires a WP plugin (free).

### Option C: OAuth2 / OpenID Connect

Use a WP OAuth2 plugin to enable standard OAuth flows. Most complex
but most flexible.

### Recommendation

**Option B** is implemented using the **Simple JWT Login** plugin.
Members use their normal WP login credentials.

## Self-Service Editing Scope

Members can edit:
- `bio`
- `website_url`
- `phone`
- `social_json` (Facebook, Instagram, etc.)
- `logo_url` (upload)
- `gallery_json` (upload)
- `show_city`, `show_member_since`
- `allow_connect`
- `services_csv`, `regions_csv`
- `tags_csv` (within allowed tags, not arbitrary)
- `organization`

Members **cannot** edit:
- `badges_csv` (admin only)
- `entry_type` (admin only)
- `opted_in` (can opt in, cannot opt others)
- `display_name` (synced from WP)
- `visibility_public` (derived from membership status)

## API Endpoints

```
POST /api/v1/auth/login
  → validates against WP, returns JWT

GET /api/v1/me/profile
  → returns the logged-in member's profile

PUT /api/v1/me/profile
  → update own profile (scoped fields only)

POST /api/v1/me/profile/logo
  → upload own logo

POST /api/v1/me/profile/gallery
  → upload own gallery images
```

## Data Sync Considerations

When a member edits their profile via our API:
- Changes are stored in our SQLite DB immediately
- Changes are **not** pushed back to WordPress (our DB owns enrichment)
- The next WP sync preserves these local changes (Task 8 merge strategy)

If we later want to push changes back to WordPress:
- Use the MemberPress API `PUT /wp-json/mp/v1/members/:id` to update
  custom fields
- Only push fields that have a WP equivalent (e.g., `url`, `profile`
  custom fields)
- Risk of conflicts if the same field is edited in both places

### Recommendation

For now, do **not** push enrichment data back to WP. Our DB is the
authority for enrichment. WP is the authority for membership/billing.
This avoids sync conflicts and keeps the integration simple.

## Deliverables (when this task is picked up)

- [x] WP JWT plugin installed and configured on staging (Simple JWT Login — configured via wp-admin, no SSH needed)
- [x] `POST /api/v1/auth/login` endpoint
- [x] JWT-based session management (NaBA session JWTs issued after WP login verification)
- [x] `GET /api/v1/me/profile` endpoint
- [x] `PUT /api/v1/me/profile` with field-level scoping
- [x] Self-service image upload endpoints (`POST /api/v1/me/profile/logo`, `/gallery`)
- [x] Frontend: login form + profile edit page in Astro (`/login`, `/account/profile`)
- [x] Documentation for member-facing profile editing flow
