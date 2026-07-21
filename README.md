# NaBA Member Data Visualization

Interactive choropleth map visualizing active NaBA (Natural Building Alliance) members by US state, built with Leaflet.js and Python. The repo also includes a **membership API** (FastAPI + SQLite), **WordPress/MemberPress sync**, and an **Astro** site with a public directory that can load live API data or static JSON.

## Overview

This project generates an interactive map showing the geographic distribution of active members across the United States. The map includes:

- Color-coded states based on member count
- Interactive hover tooltips with member counts
- Statistics panel showing total members, breakdown by state, Canada, and international members
- Click-to-zoom functionality

## Dev Setup

### Prerequisites

- Python 3.8+
- Node.js (for Astro)

### Installation

```bash
pip install -r requirements.txt
```

## WordPress → API → Astro (directory)

Staging WordPress (Hostinger) exposes the **MemberPress REST API**. Data can flow into the directory in three ways:

1. **Sync to SQLite (recommended default)** — `python -m scripts.sync_from_wordpress` pulls members into `data/membership.db`. FastAPI serves `GET /api/v1/public/members` from SQLite (`DATA_SOURCE=sqlite`).
2. **Live WordPress proxy** — Set `DATA_SOURCE=wordpress` and `WP_API_URL` / `WP_API_KEY` so the API builds the public list from MemberPress on each request (no local DB writes for reads).
3. **Static export** — After sync, `python -m scripts.export_directory_json` writes `astro-app/public/data/directoryEntries.json` for static builds.

The Astro page `astro-app/src/pages/directory.astro` uses **hybrid** behavior: it ships with fallback JSON and, when `PUBLIC_MEMBERSHIP_API_URL` is set (or in dev, `http://localhost:8000`), fetches the API in the browser and replaces the grid.

Environment variables are documented in `.env.schema`. Varlock merges `.env`, `.env.local`, then `.env.<APP_ENV>` (for example `.env.test`, `.env.prod` — `prod` is treated as production). Set **`APP_ENV`** in the shell or in `.env` / `.env.local`, then run `npx varlock run -- <command>` to inject validated env.

### Typical local workflow

```bash
# From repo root (example: production WordPress — uses .env.prod)
APP_ENV=production npx varlock run -- python -m scripts.sync_from_wordpress
APP_ENV=production npx varlock run -- uvicorn api.main:app --reload
cd astro-app && npm install && npm run dev
# Directory: http://localhost:4321/directory
```

### Automated tests (Task 6)

```bash
pip install -r requirements.txt
python -m pytest
```

- Default run: API privacy, filters, pagination, sync idempotency, and sync error messages (isolated SQLite; no WordPress required).
- Optional integration: `RUN_INTEGRATION_E2E=1` plus `WP_API_URL` / `WP_API_KEY`; add `MEMBERSHIP_E2E_API_URL=http://localhost:8000` if the API is up.

Manual curl-style checks: `bash scripts/e2e_manual_checks.sh` (requires `WP_API_URL`, `WP_API_KEY`, and a running API).

### Deployment options

| Approach | Summary |
|----------|---------|
| **Static** | Sync → `export_directory_json` → `npm run build` → deploy `dist/` (data stale until next build). |
| **Runtime API** | Deploy FastAPI on a DigitalOcean Droplet; set `PUBLIC_MEMBERSHIP_API_URL` on Netlify; client fetches live API. |
| **Hybrid** | Deploy API + keep exported JSON as fallback (current `directory.astro` behavior). |

**Production API:** `https://api.natbuild.org` on DigitalOcean (`142.93.177.21`). See [`docs/deploy-digitalocean-droplet.md`](docs/deploy-digitalocean-droplet.md) (systemd + nginx + daily MemberPress sync).

See `docs/tasks/archive/06-e2e-testing.md` for the full checklist and `docs/plan-wp-frontend-integration.md` for architecture.

### Book recommendations gallery

Member book picks are synced from a [Google Sheet](https://docs.google.com/spreadsheets/d/11fFLkKeqcibt4PuA-IPrP8XxHef1diTUK3tz7W0w2ks/edit) into the Astro `/books` page and a WordPress-ready HTML snippet.

```bash
python -m scripts.sync_book_covers
# WordPress: paste data/books-wordpress.html into a Custom HTML block
```

Step-by-step WordPress instructions: **`docs/books-gallery-wordpress.md`**.

## Project Structure

```
├── api/                    # FastAPI app (public members, health)
├── astro-app/              # Astro site (map + directory)
├── data/                   # Local DB path (gitignored), exports
├── docs/                   # Plans, task specs, staging notes
├── docs/archive/           # Archived docs (e.g. old DO staging notes)
├── scripts/                # sync_from_wordpress, sync_book_covers, export, e2e helpers
├── tests/                  # pytest (API + sync)
├── requirements.txt
└── .env.schema             # Env contract (Varlock)
```

## Workflow

### Update the Map (Astro)

1. **Export member data as JSON**:

   ```bash
   python3 scripts/export_member_data.py "data/NaBA Members.csv"
   ```

   This creates JSON files in `astro-app/public/data/` that Astro will use.

2. **Build the Astro site**:

   ```bash
   cd astro-app
   npm run build
   ```

3. **Preview locally** (optional):

   ```bash
   cd astro-app
   npm run dev
   ```

4. **Output**: The build creates `astro-app/dist/` with the static site

### Filter Active Members (CSV)

To create a filtered CSV with only active members:

```bash
python3 scripts/filter_active_members.py "NaBA Members.csv" "Jan 2026 NaBA Active Members.csv"
```

## Deployment

- **Live Site**: [https://69673212f300a9e6ee19ffce--frabjous-basbousa-aa6660.netlify.app](https://69673212f300a9e6ee19ffce--frabjous-basbousa-aa6660.netlify.app)
- **Deploy Dashboard**: [https://app.netlify.com/projects/frabjous-basbousa-aa6660/deploys/69673212f300a9e6ee19ffce](https://app.netlify.com/projects/frabjous-basbousa-aa6660/deploys/69673212f300a9e6ee19ffce)

### Deploy Process (Astro map)

1. Export data: `python3 scripts/export_member_data.py "data/NaBA Members.csv"`
2. Build site: `cd astro-app && npm run build`
3. Deploy `astro-app/dist/` to Netlify (via drag-and-drop, Git, or CLI)

## Next Steps

- [x] Protect membership data by including CSV files in `.gitignore`
- [x] Organize repository structure (scripts in `scripts/`, archive old files)
- [x] Separate HTML, JS, and CSS into individual files
- [x] Upgrade to Astro static site generator
- [x] Publish code open source to GitHub
- [x] Publish to a proper subdomain (e.g., `members.natbuild.org`)
- [x] Add more pages for directory
- [x] WordPress/MemberPress staging on Hostinger + sync + public API + Astro integration (see `docs/plan-wp-frontend-integration.md`)
- [x] WordPress authentication + member self-service profile editing (API + `/login` + `/account/profile`)
- [x] WordPress `administrator` role unlocks directory admin (JWT `admin` claim, `/api/v1/admin/*`, directory show-all + edit UI)
- [ ] Enable JWT auth plugin on **production** WordPress (Simple JWT Login or jwt-auth) so `/api/v1/auth/login` works against live members

Historical notes on the **abandoned DigitalOcean `.wpress` staging** are in `docs/archive/wordpress-staging-notes.md`.
