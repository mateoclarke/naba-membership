# Task 2: Configure WordPress Staging for Headless API Access

## Objective

Configure the Hostinger staging WordPress instance so that external
applications (the FastAPI service and Astro frontend) can reliably
consume the MemberPress REST API.

## Prerequisites

- Task 1 completed (API key exists, endpoints verified)
- wp-admin access to staging site

## Steps

### 1. Store API credentials securely (using Varlock)

This project uses [Varlock](https://varlock.dev/) to give environment
variables a declarative schema with validation and sensitive value
protection. The schema is defined in `.env.schema` (committed to git).

**Install Varlock** (requires Node.js 22+):

```bash
npx varlock init
```

If `.env.schema` already exists, Varlock will detect it. Otherwise, it
will create one from any existing `.env.example`.

**Create your local `.env`** (gitignored):

```bash
# .env (DO NOT COMMIT — holds actual secret values)
WP_API_URL=https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1
WP_API_KEY=your_memberpress_api_key_here
```

The `.env.schema` file defines the shape and constraints:

```env-spec
# @defaultSensitive=false
# @defaultRequired=false
# ---

# @type=url(prependHttps=true) @required
WP_API_URL=

# @type=string @required @sensitive
WP_API_KEY=

# @type=enum(sqlite, wordpress)
DATA_SOURCE=sqlite
```

**Validate your `.env`** at any time:

```bash
npx varlock load
```

**Run scripts with validated env vars:**

```bash
npx varlock run -- python -m scripts.sync_from_wordpress
npx varlock run -- uvicorn api.main:app --reload
```

Add to `.gitignore` if not already present:

```
.env
.env.local
.env.*.local
```

### 2. Configure CORS on WordPress

The Astro dev server (`localhost:4321`) and the FastAPI service need to
make cross-origin requests to the WP REST API during development. There
are several approaches:

#### Option A: WordPress CORS plugin (simplest)

Install and configure a CORS plugin in wp-admin:

1. Go to **Plugins → Add New**
2. Search for **"WP CORS"** or **"CORS"**
3. Install and activate
4. Configure allowed origins:
   - `http://localhost:4321` (Astro dev)
   - `http://localhost:8000` (FastAPI dev)
   - The production Astro URL when deployed

#### Option B: Custom `functions.php` snippet

Add to the active theme's `functions.php` or use a code snippets plugin:

```php
add_action('rest_api_init', function () {
    remove_filter('rest_pre_serve_request', 'rest_send_cors_headers');
    add_filter('rest_pre_serve_request', function ($value) {
        $allowed_origins = [
            'http://localhost:4321',
            'http://localhost:8000',
            'https://your-astro-site.netlify.app',
        ];

        $origin = get_http_origin();
        if (in_array($origin, $allowed_origins, true)) {
            header('Access-Control-Allow-Origin: ' . $origin);
            header('Access-Control-Allow-Methods: GET, OPTIONS');
            header('Access-Control-Allow-Headers: MEMBERPRESS-API-KEY, Content-Type');
            header('Access-Control-Allow-Credentials: true');
        }

        return $value;
    });
}, 15);
```

#### Option C: Proxy through FastAPI (recommended for production)

In production, the Astro frontend should **not** call WordPress directly.
Instead, requests go through the FastAPI service which has the API key
server-side. This avoids exposing the API key in the browser and removes
CORS issues entirely.

For development, CORS is still useful for testing the WP API directly.

### 3. Verify API security

Confirm that:

- [ ] Unauthenticated requests to `/wp-json/mp/v1/members` are rejected
  (returns 401 or empty)
- [ ] Authenticated requests with the API key header work correctly
- [ ] The API key is **not** exposed in any client-side code

Test:

```bash
# Should fail or return empty
curl -s "https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1/members"

# Should succeed
curl -s \
  -H "MEMBERPRESS-API-KEY: YOUR_KEY" \
  "https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1/members?per_page=2"
```

### 4. Disable unnecessary public REST API exposure

By default, WordPress exposes `/wp-json/wp/v2/users` which can leak
usernames. Consider disabling this on staging:

1. Install **Disable REST API** plugin, or
2. Add to `functions.php`:

```php
add_filter('rest_endpoints', function ($endpoints) {
    if (isset($endpoints['/wp/v2/users'])) {
        unset($endpoints['/wp/v2/users']);
    }
    if (isset($endpoints['/wp/v2/users/(?P<id>[\d]+)'])) {
        unset($endpoints['/wp/v2/users/(?P<id>[\d]+)']);
    }
    return $endpoints;
});
```

### 5. Configure staging-specific settings

- [ ] **Disable outgoing emails** — install "Disable Emails" plugin so
  staging doesn't email real members
- [ ] **Switch payment gateways to test/sandbox mode** (MemberPress →
  Settings → Payments)
- [ ] **Discourage search indexing** — Settings → Reading → check
  "Discourage search engines"

### 6. Test end-to-end API access

From your local machine, verify the full round-trip:

```bash
# Fetch members from staging
curl -s \
  -H "MEMBERPRESS-API-KEY: YOUR_KEY" \
  "https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1/members?per_page=5" \
  | python3 -c "import sys, json; data=json.load(sys.stdin); print(f'{len(data)} members returned')"
```

## Deliverables

- [ ] Varlock initialized (`npx varlock init`)
- [ ] `.env.schema` committed with typed, documented env vars
- [ ] `.env` file created with WP API credentials (gitignored)
- [ ] `npx varlock load` validates without errors
- [ ] `.gitignore` updated to exclude `.env` files
- [ ] CORS configured for dev origins (or decision to proxy only)
- [ ] API security verified (auth required for member data)
- [ ] Staging-specific safety settings applied (no emails, sandbox
  payments, no indexing)
- [ ] API accessible from local development machine

## Architecture Note

```
                    ┌─────────────────────┐
                    │  WordPress Staging   │
                    │  (Hostinger)         │
                    │                     │
                    │  MemberPress API    │
                    │  /wp-json/mp/v1/    │
                    └─────────┬───────────┘
                              │ HTTPS + API key
                              ▼
                    ┌─────────────────────┐
                    │  FastAPI Service    │
                    │  (localhost:8000)    │
                    │                     │
                    │  - Sync script OR   │
                    │  - Live proxy       │
                    │  - SQLite cache     │
                    └─────────┬───────────┘
                              │ HTTP (CORS)
                              ▼
                    ┌─────────────────────┐
                    │  Astro Frontend     │
                    │  (localhost:4321)    │
                    └─────────────────────┘
```
