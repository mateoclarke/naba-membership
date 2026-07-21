# Task 5: Update Astro Frontend for WordPress-Backed API

## Objective

Configure the Astro frontend to consume directory data from the
WordPress-backed FastAPI service and verify that real member data renders
correctly.

## Prerequisites

- A running FastAPI instance with public members (typically SQLite filled via Task 3 sync or CSV seed). Task 4’s config is optional for this task; the Astro page only needs the same JSON shape from `GET /api/v1/public/members/`.
- Existing codebase:
  - `astro-app/src/pages/directory.astro` — Directory page with
    client-side API fetch + static JSON fallback
  - `astro-app/public/data/directoryEntries.json` — Static fallback data

## Current Behavior

The directory page already supports two data paths:

1. **Static fallback:** Imports `directoryEntries.json` at build time
   for SSG rendering
2. **API fetch:** Client-side JavaScript fetches from `apiBaseUrl +
   '/api/v1/public/members?page_size=500'` and re-renders the cards

The `apiBaseUrl` is set via:
- `PUBLIC_MEMBERSHIP_API_URL` env var, or
- `http://localhost:8000` in dev mode, or
- empty string (disabled) in production builds

## Steps

### 1. Configure environment variables

Create/update `astro-app/.env` for local development:

```bash
# astro-app/.env
PUBLIC_MEMBERSHIP_API_URL=http://localhost:8000
```

For production builds (Netlify or other):

```bash
PUBLIC_MEMBERSHIP_API_URL=https://your-api-host.com
```

### 2. Update the static fallback data

After running the sync script (Task 3), regenerate the static JSON
fallback so the SSG build has fresh data:

Create or update a build script that:

1. Calls `GET /api/v1/public/members?page_size=500` from the local
   FastAPI
2. Maps the response to the `DirectoryEntry` shape
3. Writes to `astro-app/public/data/directoryEntries.json`

```python
# scripts/export_directory_json.py
"""
Export directory data from the API to a static JSON file for Astro SSG builds.

Usage:
    python -m scripts.export_directory_json
"""
import json
import requests

API_URL = "http://localhost:8000/api/v1/public/members"
OUTPUT = "astro-app/public/data/directoryEntries.json"

def export():
    resp = requests.get(API_URL, params={"page_size": 500})
    resp.raise_for_status()
    data = resp.json()

    entries = []
    for item in data["items"]:
        entries.append({
            "id": item["id"],
            "name": item["display_name"],
            "type": item["entry_type"],
            "role": item.get("role") or "Member",
            "org": item.get("organization"),
            "location": item.get("location_display") or "",
            "website": item.get("website_url"),
            "tags": item.get("tags", []),
        })

    with open(OUTPUT, "w") as f:
        json.dump(entries, f, indent=2)

    print(f"Exported {len(entries)} entries to {OUTPUT}")

if __name__ == "__main__":
    export()
```

### 3. Verify field mapping

The client-side `mapApiItemToEntry` function in `directory.astro`
already handles the API → display mapping:

```javascript
function mapApiItemToEntry(item) {
    return {
        id: item.id,
        name: item.display_name || '',
        type: item.entry_type || 'individual',
        role: item.role || 'Member',
        org: item.organization || undefined,
        location: item.location_display || ...,
        website: item.website_url ? String(item.website_url) : undefined,
        tags: Array.isArray(item.tags) ? item.tags : []
    };
}
```

Verify that the WP-sourced API responses include all these fields with
correct values. Check for:

- [ ] `display_name` is populated (not empty or just a username)
- [ ] `entry_type` is one of `individual`, `organization`, `business`
- [ ] `location_display` is formatted nicely (e.g. "Taos, NM (US)")
- [ ] `website_url` is a valid URL or null
- [ ] `tags` are meaningful (not empty for most members)
- [ ] `member_since_year` is reasonable

### 4. Test the full flow locally

```bash
# Terminal 1: Start the API
cd /path/to/naba-membership
uvicorn api.main:app --reload

# Terminal 2: Start Astro dev server
cd astro-app
npm run dev

# Open http://localhost:4321/directory
# Should show real member data fetched from the API
```

### 5. Handle pagination for large member lists

The current client-side fetch requests `page_size=500`. If there are
more than 500 members, consider:

- Increasing `page_size` (the API currently allows up to 500)
- Adding client-side pagination or infinite scroll
- Fetching all pages in sequence

For now, 500 should cover the NaBA membership size. If the member count
grows significantly, pagination will need to be added to the frontend.

### 6. Update build process for Netlify

If deploying to Netlify, the build command should:

1. Start the API server
2. Run the export script to generate static JSON
3. Build the Astro site
4. Deploy the `dist/` folder

Or, configure `PUBLIC_MEMBERSHIP_API_URL` as a Netlify env var pointing
to the deployed API, so the client-side fetch works at runtime.

## Deliverables

- [ ] `astro-app/.env` configured for local dev
- [ ] `scripts/export_directory_json.py` created for static builds
- [ ] Verified real WP member data renders correctly on the directory page
- [ ] Both Membership Directory and Business Directory views work
- [ ] Search/filter (if implemented) works with WP-sourced data
- [ ] Build process documented for static and runtime modes

## Screenshots / Verification

After completing this task, verify:

1. Open `http://localhost:4321/directory` — shows member cards
2. Toggle between Membership Directory and Business Directory
3. Cards show: name, role/membership tier, location, website link, tags
4. Data matches what's in the WordPress staging admin
