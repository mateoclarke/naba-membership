# Task 1: Discover & Document the MemberPress REST API

## Objective

Verify that the MemberPress REST API is accessible on the Hostinger
staging site and document the actual response shapes, available fields,
and any NaBA-specific custom fields.

## Prerequisites

- Access to wp-admin at
  `https://mediumturquoise-crab-432395.hostingersite.com/wp-admin/`
- MemberPress plugin installed and activated (confirmed — members are
  visible at admin → MemberPress → Members)

## Steps

### 1. Verify MemberPress Developer Tools add-on

The REST API requires the **Developer Tools** add-on. In wp-admin:

1. Go to **MemberPress → Add-ons**
2. Look for **Developer Tools**
3. If not installed, click **Install** then **Activate**
4. If the add-on is not available, check the MemberPress license tier —
   Developer Tools requires **Plus**, **Pro**, or **Scale** plan

The add-on provides:
- REST API endpoints at `/wp-json/mp/v1/`
- API key management (MemberPress → Settings → Developer Tools tab)
- Built-in API documentation & testing UI within wp-admin

### 2. Generate an API key

1. Go to **MemberPress → Settings → Developer Tools** tab
2. Click **Generate API Key** (or copy existing one)
3. Store the key securely — it will be used in `.env` files for the sync
   script and FastAPI service
4. **Do not commit the API key to git**

### 3. Test the members endpoint

Using `curl` or a tool like Postman, test the following:

```bash
# List members (first page)
curl -s \
  -H "MEMBERPRESS-API-KEY: YOUR_KEY_HERE" \
  "https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1/members?per_page=5" \
  | python3 -m json.tool

# Single member detail
curl -s \
  -H "MEMBERPRESS-API-KEY: YOUR_KEY_HERE" \
  "https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1/members/MEMBER_ID" \
  | python3 -m json.tool

# List membership plans
curl -s \
  -H "MEMBERPRESS-API-KEY: YOUR_KEY_HERE" \
  "https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1/memberships" \
  | python3 -m json.tool
```

### 4. Document actual response fields

For each endpoint, record:

- The full JSON structure of a sample response
- Any NaBA-specific custom profile fields (the `profile` object may
  contain custom MemberPress fields like `mepr_company_name`,
  `mepr_birthday`, etc.)
- Pagination behavior (`page`, `per_page`, total count headers)
- Any fields in the address object that NaBA members actually populate

### 5. Create a field mapping table

Map WP/MemberPress fields → existing `DirectoryProfile` schema:

| MemberPress field | DirectoryProfile field | Notes |
|-------------------|----------------------|-------|
| `id` | `member_id` | |
| `first_name` + `last_name` | `display_name` | Concatenate |
| `display_name` | `display_name` | Fallback |
| `address.mepr-address-city` | `city` | |
| `address.mepr-address-state` | `state_province` | |
| `address.mepr-address-country` | `country` | |
| `url` | `website_url` | Member's website |
| `active_memberships[0].title` | `role` / tags | Derive tier |
| `first_txn.created_at` | `member_since_year` | Parse year |
| `profile.*` | tags / role | Custom fields |
| `registered_at` | `member_since_year` | Fallback |

### 6. Check rate limits and pagination

- Test with `per_page=100` (or higher) to see max allowed
- Check response headers for total count (`X-WP-Total`,
  `X-WP-TotalPages` or MemberPress equivalents)
- Note any rate limiting

## Deliverables

- [ ] Confirmed Developer Tools add-on is active
- [ ] API key generated and stored in `.env` (gitignored)
- [ ] Sample JSON responses saved (e.g. `docs/samples/mp-member.json`)
  for reference during development — redact real PII
- [ ] Field mapping table completed
- [ ] Pagination and rate limit behavior documented
- [ ] List of NaBA-specific custom fields identified

## Notes

- The Developer Tools add-on also provides **webhooks** (event triggers)
  for member creation, update, and deletion. These could be used later
  for real-time sync but are not needed for Task 1.
- If the Developer Tools add-on is not available on the current license,
  the fallback is the standard WordPress REST API (`/wp-json/wp/v2/users`)
  which has basic user data but lacks MemberPress-specific fields like
  memberships, transactions, and custom profile fields.
