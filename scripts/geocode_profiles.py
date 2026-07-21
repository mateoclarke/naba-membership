"""
Batch geocode opted-in directory profiles missing coordinates.

Uses OpenStreetMap Nominatim with conservative rate limiting
(1 request/second) and writes lat/lng back to `directory_profiles`.

Usage:
    python -m scripts.geocode_profiles
    python -m scripts.geocode_profiles --limit 50
    python -m scripts.geocode_profiles --dry-run
"""

from __future__ import annotations

import argparse
import time
from typing import Optional

import requests
from sqlalchemy import select

from api.db import SessionLocal, engine, ensure_directory_profile_geocode_columns
from api.models import DirectoryProfile


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "naba-membership-map-geocoder/1.0 (local-dev)"
REQUEST_TIMEOUT_SECONDS = 15
SECONDS_PER_REQUEST = 1.05


def build_query(profile: DirectoryProfile) -> Optional[str]:
    parts = [profile.city, profile.state_province, profile.country]
    tokens = [str(p).strip() for p in parts if p and str(p).strip()]
    if not tokens:
        return None
    return ", ".join(tokens)


def geocode_location(query: str) -> Optional[tuple[float, float]]:
    response = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload:
        return None
    top = payload[0]
    try:
        lat = float(top["lat"])
        lng = float(top["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    return (lat, lng)


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode directory profiles.")
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of profiles to geocode this run (0 = no limit).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve coordinates but do not write to database.",
    )
    args = parser.parse_args()

    ensure_directory_profile_geocode_columns(engine)

    db = SessionLocal()
    try:
        rows = (
            db.execute(
                select(DirectoryProfile).where(
                    DirectoryProfile.opted_in.is_(True),
                    DirectoryProfile.latitude.is_(None),
                    DirectoryProfile.longitude.is_(None),
                )
            )
            .scalars()
            .all()
        )
        if args.limit and args.limit > 0:
            rows = rows[: args.limit]

        if not rows:
            print("No profiles need geocoding.")
            return

        print(f"Geocoding {len(rows)} profile(s)...")
        success = 0
        not_found = 0
        failed = 0

        for idx, profile in enumerate(rows, start=1):
            query = build_query(profile)
            if not query:
                print(f"[{idx}/{len(rows)}] {profile.id}: skipped (no location fields)")
                not_found += 1
                continue

            try:
                coords = geocode_location(query)
            except requests.RequestException as exc:
                print(f"[{idx}/{len(rows)}] {profile.id}: request failed ({exc})")
                failed += 1
                time.sleep(SECONDS_PER_REQUEST)
                continue

            if not coords:
                print(f"[{idx}/{len(rows)}] {profile.id}: not found for '{query}'")
                not_found += 1
                time.sleep(SECONDS_PER_REQUEST)
                continue

            lat, lng = coords
            print(f"[{idx}/{len(rows)}] {profile.id}: {query} -> ({lat:.6f}, {lng:.6f})")

            if not args.dry_run:
                profile.latitude = lat
                profile.longitude = lng
            success += 1
            time.sleep(SECONDS_PER_REQUEST)

        if not args.dry_run:
            db.commit()
        print(
            f"Done. success={success}, not_found={not_found}, failed={failed}, dry_run={args.dry_run}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
