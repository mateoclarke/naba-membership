# Book recommendations gallery — WordPress guide

NaBA’s book list is maintained in a **Google Sheet**, synced by a Python script, and published either on the **Astro site** (`/books`) or on **WordPress** via a paste-ready HTML file.

This guide walks through updating the list and adding it to WordPress.

## How it fits together

```text
Google Sheet (source of truth)
        │
        ▼
python -m scripts.sync_book_covers
        │
        ├── astro-app/public/data/books.json      → Astro /books page
        ├── astro-app/public/images/book-covers/  → local cover files (Astro)
        └── data/books-wordpress.html             → paste into WordPress
```

The WordPress export is **self-contained**: cover images load from Open Library and Amazon URLs embedded in the HTML. You do **not** need to upload cover images to the WordPress Media Library.

Purchase buttons link to each row’s **eCommerce link** column (Bookshop.org, Amazon, publisher site, etc.).

## 1. Maintain the Google Sheet

**Sheet ID (default):** `11fFLkKeqcibt4PuA-IPrP8XxHef1diTUK3tz7W0w2ks`

Expected columns (header names are flexible; the script matches common variants):

| Column | Purpose |
|--------|---------|
| Title | Book title |
| Author | Author name(s) |
| Publisher | Optional |
| ISBN | ISBN-10 or ISBN-13 |
| EAN/UPC | Same as ISBN-13 for most books; used if ISBN is blank |
| Past Conference Speaker (Y/N) | Optional badge |
| eCommerce link | **Required for working buy links** — full `https://…` URL |

**Sharing:** The sheet must be readable for export. Use **Share → General access → Anyone with the link → Viewer**, or set `GOOGLE_API_KEY` (Sheets API) in your environment.

**eCommerce links:** Paste the full product URL from Bookshop, Amazon, or another store. For Bookshop, copy the URL from the browser bar (including `?ean=…`). The script preserves that `ean` and does not replace it with the ISBN column when both differ.

## 2. Generate the WordPress HTML (on your machine)

From the repo root:

```bash
pip install -r requirements.txt
python -m scripts.sync_book_covers
```

Optional flags:

```bash
# Re-download all cover images (Astro only; WP HTML uses remote image URLs)
python -m scripts.sync_book_covers --force-covers

# Skip cover downloads (faster; only refreshes JSON + WordPress HTML)
python -m scripts.sync_book_covers --skip-download

# Use a local CSV/ODS instead of Google Sheets
python -m scripts.sync_book_covers --source "data/Book suggestions for Country Bookshelf.ods"
```

When sync succeeds you should see:

```text
Processed N books
  JSON: .../astro-app/public/data/books.json
  WordPress HTML: .../data/books-wordpress.html
```

Open `data/books-wordpress.html` in a text editor and confirm the links and titles look correct before pasting into WordPress.

## 3. Add the gallery to WordPress (block editor)

### Create or edit a page

1. Log in to WordPress admin.
2. Go to **Pages → Add New** (or edit an existing page, e.g. “Book recommendations”).
3. Set a **title** for the page (e.g. “Natural Building Alliance Book Recommendations”).  
   The pasted HTML includes its own heading; you can leave the page title matching or hide the theme’s duplicate title if your theme shows both.

### Paste the HTML block

1. Click **+** to add a block.
2. Search for **Custom HTML** and insert it.
3. Open `data/books-wordpress.html` from this repo.
4. Select **all** contents (from the opening `<!-- NaBA book gallery` comment through the closing `</div>`) and copy.
5. Paste into the Custom HTML block.

### Preview and publish

1. Click **Preview** and check:
   - Grid layout and cover images load
   - A **Bookshop.org** book opens the correct Bookshop page
   - An **Amazon** or other link shows **Buy online** and opens the right site
2. Choose a **full-width** page template if your theme offers one (helps the grid use horizontal space).
3. Click **Publish** or **Update**.

### Use `/books` as the page URL

WordPress builds the URL from the page **slug**, not from the pasted HTML.

1. **Pages →** open your book recommendations page.
2. In the right sidebar (**Page** settings), find **URL** / **Permalink**.
3. Change the slug from `natural-building-alliance-book-recommendations` to **`books`**.
4. Confirm the permalink preview shows `https://natural-building-alliance.org/books/`.
5. Click **Update**.

If WordPress says the slug is already taken, another page or post is using `/books` — rename or trash that item first, or pick a different slug (e.g. `book-recommendations`).

**Optional — redirect the old URL:** After the slug change, the old link  
`https://natural-building-alliance.org/natural-building-alliance-book-recommendations/`  
will 404 unless you add a redirect. Use a plugin such as **Redirection** (301 from the old path to `/books/`), or your host’s redirect rules.

**Duplicate heading:** Your theme may show the page title above the pasted gallery, which also includes an `<h2>`. Hide the theme title (many themes: **Page → disable title**) or remove the `<h2>` block from the pasted HTML so only one main heading appears.

### Add to navigation (optional)

1. **Appearance → Menus** (or **Editor → Navigation** in block themes).
2. Add the new page to the main menu.
3. Save the menu.

## 4. Updating the list later

Whenever the Google Sheet changes:

1. Run `python -m scripts.sync_book_covers` again.
2. Copy the **entire** updated `data/books-wordpress.html`.
3. In WordPress, edit the page, select the Custom HTML block, replace all HTML, and **Update**.

There is no automatic WordPress sync; the HTML file is the handoff artifact.

## 5. Astro site (optional)

The same sync powers the Astro gallery at `/books`:

```bash
python -m scripts.sync_book_covers
cd astro-app && npm run dev
# http://localhost:4321/books
```

Deploy Astro separately from WordPress if you use both.

## Optional: Bookshop affiliate ID

If NaBA has a Bookshop.org affiliate ID, set it when syncing so new generated links (not sheet links that already include parameters) can include `aid=`:

```bash
export BOOKSHOP_AFFILIATE_ID=your_id
python -m scripts.sync_book_covers
```

Links copied from the **eCommerce link** column are left as-is except for ensuring `next=t`.

## Troubleshooting

| Problem | What to check |
|--------|----------------|
| Sync can’t read Google Sheet | Share sheet as Viewer, or set `GOOGLE_API_KEY`; script falls back to local ODS if present |
| Bookshop link 404 or wrong edition | **eCommerce link** `ean=` must match the listing; don’t rely on ISBN column alone if editions differ |
| Button says “Buy on Bookshop.org” but link fails | Open the URL from `books-wordpress.html` in a private browser window; fix the URL in the sheet and re-sync |
| Covers missing in WordPress HTML | Re-run sync; covers use Open Library / Amazon URLs in the HTML. If still missing, add/fix ISBN or EAN in the sheet |
| Theme strips layout | Use Custom HTML block (not “Code” in a paragraph); try a full-width template; avoid pasting inside columns that constrain width |
| Duplicate page title | Hide theme page title or remove the `<h2>` inside the pasted HTML (keep one title only) |

## Related files

| File | Role |
|------|------|
| `scripts/sync_book_covers.py` | Sync script |
| `data/books-wordpress.html` | Paste into WordPress |
| `astro-app/public/data/books.json` | Data for Astro `/books` |
| `astro-app/src/pages/books.astro` | Astro gallery page |

## ISBN vs EAN (quick reference)

For books, **EAN-13** and **ISBN-13** are usually the same 13-digit number. **ISBN-10** is an older format; Amazon cover lookups often use ISBN-10 internally. The sheet’s **EAN/UPC** and **ISBN** columns both help the sync script find covers; **eCommerce link** controls where the buy button goes.
