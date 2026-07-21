# Astro Starter Kit: Minimal

```sh
npm create astro@latest -- --template minimal
```

> 🧑‍🚀 **Seasoned astronaut?** Delete this file. Have fun!

## 🚀 Project Structure

Inside of your Astro project, you'll see the following folders and files:

```text
/
├── public/
├── src/
│   └── pages/
│       └── index.astro
└── package.json
```

Astro looks for `.astro` or `.md` files in the `src/pages/` directory. Each page is exposed as a route based on its file name.

There's nothing special about `src/components/`, but that's where we like to put any Astro/React/Vue/Svelte/Preact components.

Any static assets, like images, can be placed in the `public/` directory.

## 🧞 Commands

All commands are run from the root of the project, from a terminal:

| Command                   | Action                                           |
| :------------------------ | :----------------------------------------------- |
| `npm install`             | Installs dependencies                            |
| `npm run dev`             | Starts local dev server at `localhost:4321`      |
| `npm run build`           | Build your production site to `./dist/`          |
| `npm run preview`         | Preview your build locally, before deploying     |
| `npm run astro ...`       | Run CLI commands like `astro add`, `astro check` |
| `npm run astro -- --help` | Get help using the Astro CLI                     |

## Directory page and membership API

The **Directory** page (`/directory`) shows the membership and business directory. It uses:

- **Seed data:** `public/data/directoryEntries.json` for the initial render and when the API is unavailable.
- **Live data:** When `PUBLIC_MEMBERSHIP_API_URL` is set (or in dev it defaults to `http://localhost:8000`), the page fetches from `GET /api/v1/public/members/?page_size=500` and replaces the list with API data.

### Local development

1. From the repo root, start the API: `uvicorn api.main:app --reload` (or `npx varlock run -- uvicorn api.main:app --reload`).
2. From `astro-app/`, run `npm run dev` and open `http://localhost:4321/directory`.

Optional: copy `.env.example` to `.env` and set `PUBLIC_MEMBERSHIP_API_URL` if your API is not on `http://localhost:8000`. In dev, Astro still defaults the directory page to `http://localhost:8000` when the variable is unset.

### Member account (login + profile)

Requires the API with WordPress JWT and `AUTH_JWT_SECRET` configured (`POST /api/v1/auth/login`, `/api/v1/me/*`).

- **`/login`** — Sign in with NaBA website username and password; stores the API session token in `localStorage`.
- **`/account/profile`** — View and edit your directory profile (text fields, logo, gallery). Unauthenticated users see a link to sign in.

Use the same `PUBLIC_MEMBERSHIP_API_URL` as the directory. CORS on the API must allow the Astro origin (e.g. `http://localhost:4321`).

### Static JSON for production builds (SSG)

To refresh `public/data/directoryEntries.json` from a running API (e.g. after syncing WordPress → SQLite), from the **repo root**:

```bash
npx varlock run -- python -m scripts.export_directory_json
```

From `astro-app/` you can also run `npm run export-directory` (same script; ensure the API is reachable).

Or with `PUBLIC_MEMBERSHIP_API_URL` already in the environment. The script paginates until all public members are exported.

### Netlify / hosted builds

- **Runtime:** Set `PUBLIC_MEMBERSHIP_API_URL` in the site host’s environment to your deployed API URL so the browser can fetch live directory data on `/directory`.
- **SSG-only:** Run the export script during the build (with the API reachable from the build environment), then `npm run build` so the static JSON matches the API at build time.

## 👀 Want to learn more?

Feel free to check [our documentation](https://docs.astro.build) or jump into our [Discord server](https://astro.build/chat).
