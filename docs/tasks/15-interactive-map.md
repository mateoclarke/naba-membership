# Task 15: Interactive Map Enhancements

## Objective

Make the map page a first-class way to explore the membership — not
just pins on a map, but an interactive tool that connects geographic
data to the member and business directory.

## Background

The board liked the existing Leaflet map and wants more interactivity:
clicking a state or region should filter a list of members, and members
should be plottable as markers.

---

## Features

### 1. Member markers on the map

**Current state:** The map exists but may use static data or limited
member info.

**Goal:** Plot opted-in members (and businesses) as markers using their
`city`, `state_province`, `country` fields geocoded to lat/lng.

**Approach:**
- Add `latitude` and `longitude` columns to `DirectoryProfile` (nullable).
- Populate during sync or via a geocoding script using a free service
  (e.g., Nominatim / OpenStreetMap — no API key needed, just rate
  limiting).
- Markers use different icons/colors for:
  - Individual members
  - Businesses
  - Educators (if Task 14 categories are implemented)

### 2. Click state/region → filter members

**Goal:** Clicking a US state (or country for international members)
filters a sidebar or bottom panel showing members in that area.

**Approach options:**

**Option A: GeoJSON state boundaries (recommended)**
- Load US state boundaries as a GeoJSON layer.
- On click, highlight the state and filter the member list.
- Show a panel/sidebar with matching members as compact cards.
- URL updates to `/map?state=CO` for shareable links.

**Option B: Cluster markers + popup list**
- Use Leaflet MarkerCluster.
- Clicking a cluster at state-level zoom shows a list of members.
- Simpler but less visually polished.

**Recommendation:** Start with Option A for US states, fall back to
markers for international members.

### 3. Map ↔ Directory interaction

- Clicking a member card in the directory could scroll/zoom the map to
  that member's location (if on the map page).
- Clicking a map marker shows a popup with the member's name, role,
  and a "View profile" link.
- Filters applied on the directory page (material, category) could
  also apply on the map.

### 4. Material/category map layers (stretch)

- Toggle map layers by material (e.g., "Show all straw bale builders")
  using the taxonomy from Task 14.
- Each material could have a distinct marker color.

---

## Data Model Changes

```python
# Add to DirectoryProfile
latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
```

## Geocoding Strategy

- Use Nominatim (free, no API key): `city, state_province, country`
  → lat/lng.
- Rate limit: 1 request/second (Nominatim policy).
- Run as a batch script: `scripts/geocode_profiles.py`
- Cache results — only geocode profiles with location but no lat/lng.
- ~582 members = ~10 minutes at 1 req/sec.

---

## API Changes

- Add `latitude` and `longitude` to `DirectoryProfileListItem` schema.
- Add a `GET /api/v1/public/members/map` endpoint that returns all
  opted-in members with coordinates as a lightweight GeoJSON or flat
  array (id, name, lat, lng, entry_type, categories, materials).

---

## UI Implementation

### Map page (`/map`)

- Load member markers from the API on page load.
- Add GeoJSON layer for US state boundaries.
- Sidebar or bottom panel shows filtered member list.
- State click → highlight + filter.
- Marker click → popup card with name, type, "View profile" link.

### Shared filters

- If material/category filters exist (Task 14), show them on the map
  page too.
- Selecting a filter updates both the marker layer and the sidebar list.

---

## Deliverables

- [x] Add `latitude`, `longitude` columns to `DirectoryProfile`
- [x] Create `scripts/geocode_profiles.py` (Nominatim batch geocoder)
- [x] Add map-specific API endpoint (lightweight coordinate data)
- [x] Add member markers to the Leaflet map
- [x] Add US state GeoJSON layer with click-to-filter
- [x] Add sidebar/panel showing filtered member cards
- [x] Add marker popups with member info and profile link
- [x] URL state sync (`/map?state=CO`)
- [ ] (Stretch) Material/category layer toggles
