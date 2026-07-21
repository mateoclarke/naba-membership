# Plan: Connect WordPress Staging to Astro Frontend

## Overview

With the Hostinger-hosted WordPress staging instance now live at
`https://mediumturquoise-crab-432395.hostingersite.com/`, the goal is to
replace the CSV-seeded SQLite data source with **live MemberPress data**
from WordPress, flowing through the existing FastAPI layer into the Astro
frontend.

## Current Architecture

```
CSV export ──► seed script ──► SQLite DB ──► FastAPI ──► Astro frontend
```

## Target Architecture

```
WordPress/MemberPress ──► REST API ──► sync script ──► SQLite DB ──► FastAPI ──► Astro frontend
                                   (or)
WordPress/MemberPress ──► REST API ──► FastAPI (live proxy) ──► Astro frontend
```

The **sync approach** (periodic pull from WP into SQLite) is recommended
initially because it:

- Keeps the Astro frontend shape unchanged (same FastAPI responses)
- Avoids coupling the frontend to WordPress uptime
- Lets us run the directory as a static build if needed
- Preserves the privacy layer (WP data is filtered before reaching the public API)

## Staging WordPress Instance

| Detail | Value |
|--------|-------|
| **URL** | `https://mediumturquoise-crab-432395.hostingersite.com/` |
| **Admin** | `https://mediumturquoise-crab-432395.hostingersite.com/wp-admin/` |
| **MemberPress** | Installed (members visible at admin → MemberPress → Members) |
| **REST API base** | `https://mediumturquoise-crab-432395.hostingersite.com/wp-json/mp/v1/` |
| **Provider** | Hostinger |

## Task Breakdown

Each task has a dedicated doc in `docs/tasks/` with enough detail to hand
off to a sub-agent.

**Status:** Tasks 1–6 are implemented in this repo (MemberPress client, sync script, `DATA_SOURCE` / live WP path in FastAPI, Astro directory fetch + fallback JSON, pytest coverage and manual e2e doc).

| # | Task | File | Dependencies |
|---|------|------|-------------|
| 1 | Discover & document the MemberPress REST API | `docs/tasks/01-discover-memberpress-api.md` | Staging WP access |
| 2 | Configure WordPress for headless API access | `docs/tasks/02-configure-wp-headless.md` | Task 1 |
| 3 | Build a WordPress → SQLite sync script | `docs/tasks/03-wp-sync-script.md` | Task 2 |
| 4 | Add WP data source config to FastAPI | `docs/tasks/04-fastapi-wp-datasource.md` | Task 3 |
| 5 | Update Astro frontend for WP-backed API | `docs/tasks/05-astro-wp-integration.md` | Task 4 |
| 6 | End-to-end integration testing | `docs/tasks/06-e2e-testing.md` | Task 5 |

## Key Decisions

1. **Sync vs. live proxy:** Start with sync (script pulls WP data into
   SQLite on demand). Can add live proxy later if real-time freshness
   matters.
2. **MemberPress API access:** Requires the Developer Tools add-on (comes
   with MemberPress Plus/Pro/Scale plans) and an API key.
3. **Privacy model:** Same as today — only directory-safe fields reach
   the public API. PII stays in the internal `members` table.
4. **Hosting:** The Hostinger staging site replaces the DigitalOcean
   Docker staging that never successfully imported the full backup
   (historical notes: `docs/archive/wordpress-staging-notes.md`).
5. **Environment management:** Using [Varlock](https://varlock.dev/) for
   declarative `.env.schema` with validation, type safety, and sensitive
   value protection. The `.env.schema` file is committed to git and
   serves as the single source of truth for all environment variables
   (replaces `.env.example`). Scripts and servers are run via
   `npx varlock run -- <command>` which validates and injects env vars.

## Quick Reference — MemberPress REST API

Base path: `/wp-json/mp/v1/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/members` | GET | List members (paginated, searchable) |
| `/members/{id}` | GET | Single member detail |
| `/members` | POST | Create a member |
| `/members/{id}` | PUT | Update a member |
| `/memberships` | GET | List membership plans |
| `/transactions` | GET | List transactions |

Auth: `MEMBERPRESS-API-KEY` header.

Member response includes: `id`, `email`, `username`, `first_name`,
`last_name`, `display_name`, `registered_at`, `active_memberships[]`,
`address` (city, state, zip, country), `profile` (custom fields),
`first_txn`, `latest_txn`, `active_txn_count`, `login_count`.
