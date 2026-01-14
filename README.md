# NaBA Member Data Visualization

Interactive choropleth map visualizing active NaBA (Natural Building Alliance) members by US state, built with Leaflet.js and Python.

## Overview

This project generates an interactive map showing the geographic distribution of active members across the United States. The map includes:

- Color-coded states based on member count
- Interactive hover tooltips with member counts
- Statistics panel showing total members, breakdown by state, Canada, and international members
- Click-to-zoom functionality

## Dev Setup

### Prerequisites

- Python 3.8+
- pandas

### Installation

```bash
pip install pandas
```

## Project Structure

```
dataviz/
├── scripts/                          # Python scripts
│   ├── export_member_data.py        # NEW: exports JSON for Astro
│   ├── filter_active_members.py     # Filter CSV for active members only
│   └── clean_csv.py                 # Utility to clean CSV files
├── astro-app/                        # NEW: Astro static site generator
│   ├── src/
│   │   ├── pages/
│   │   │   └── index.astro          # Main page
│   │   ├── components/
│   │   │   └── Map.tsx              # React map component
│   │   ├── layouts/
│   │   │   └── Layout.astro          # Base layout
│   │   └── styles/
│   │       └── map.css              # Map styles
│   ├── public/
│   │   └── data/                    # JSON data files (generated)
│   │       ├── memberCounts.json
│   │       ├── stats.json
│   │       └── stateMapping.json
│   ├── dist/                        # Build output (deployed to Netlify)
│   └── netlify.toml                 # Netlify deployment config
├── archive/                          # Old/unused files (for reference)
├── README.md                         # This file
├── requirements.txt                  # Python dependencies
└── .gitignore                        # Git ignore rules (CSV files excluded)
```

## Workflow

### Update the Map (Astro - Recommended)

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

### Filter Active Members

To create a filtered CSV with only active members:

```bash
python3 scripts/filter_active_members.py "NaBA Members.csv" "Jan 2026 NaBA Active Members.csv"
```

## Deployment

- **Live Site**: [https://69673212f300a9e6ee19ffce--frabjous-basbousa-aa6660.netlify.app](https://69673212f300a9e6ee19ffce--frabjous-basbousa-aa6660.netlify.app)
- **Deploy Dashboard**: [https://app.netlify.com/projects/frabjous-basbousa-aa6660/deploys/69673212f300a9e6ee19ffce](https://app.netlify.com/projects/frabjous-basbousa-aa6660/deploys/69673212f300a9e6ee19ffce)

### Deploy Process

**Astro (Recommended):**

1. Export data: `python3 scripts/export_member_data.py "NaBA Members.csv"`
2. Build site: `cd astro-app && npm run build`
3. Deploy `astro-app/dist/` to Netlify (via drag-and-drop, Git, or CLI)

## Next Steps

- [x] Protect membership data by including CSV files in `.gitignore` ✅
- [x] Organize repository structure (scripts in `scripts/`, archive old files) ✅
- [x] Separate HTML, JS, and CSS into individual files ✅
- [x] Upgrade to Astro static site generator ✅
- [x] Publish code open source to GitHub
- [x] Publish to a proper subdomain (e.g., `members.natbuild.org`)
- [x] Add more pages for directory
- [ ] Set up Wordpress instance from data export as sandbox
- [ ] Configure headless WP API to feed directory data to Astro
- [ ] Integrate WordPress authentication for member directory editing
