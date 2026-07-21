"""
Seed the local membership database from the MemberPress CSV export.

This script should be run locally and is designed to avoid writing PII
to any JSON files or other artefacts that might be committed to git.

Usage (from repo root):

    python -m scripts.seed_members_from_csv
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete

from api.db import SessionLocal, Base, engine
from api.models import Member, DirectoryProfile


CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "NaBA Members.csv"


DATE_FORMATS = [
    "%m/%d/%y %H:%M",
    "%m/%d/%Y %H:%M",
]


def parse_date(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def build_location_display(city: str | None, state: str | None, country: str | None) -> str | None:
    parts = [p for p in [city, state] if p]
    tail = country or ""
    if parts and tail:
        return f"{', '.join(parts)} ({tail})"
    if parts:
        return ", ".join(parts)
    if tail:
        return tail
    return None


def main() -> None:
    if not CSV_PATH.exists():
        raise SystemExit(f"CSV not found at {CSV_PATH}")

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Simple strategy for now: wipe and re-seed both tables
        db.execute(delete(DirectoryProfile))
        db.execute(delete(Member))
        db.commit()

        # Use latin-1 to be tolerant of special characters in names/addresses.
        # This is only for local seeding; we never expose raw text directly.
        with CSV_PATH.open(newline="", encoding="latin-1") as f:
            reader = csv.DictReader(f)

            for row in reader:
                try:
                    member_id = int(row.get("ID") or 0)
                except ValueError:
                    continue
                if not member_id:
                    continue

                status = (row.get("status") or "").strip().lower() or "none"
                if status != "active":
                    # Only seed active members into the public directory as per spec
                    continue

                first_name = (row.get("first_name") or "").strip() or None
                last_name = (row.get("last_name") or "").strip() or None
                email = (row.get("email") or "").strip() or None
                memberships_raw = (row.get("memberships") or "").strip() or None

                country = (row.get("mepr-address-country") or "").strip() or None
                state = (row.get("mepr-address-state") or "").strip() or None
                city = (row.get("mepr-address-city") or "").strip() or None

                registered_at = parse_date(row.get("registered") or "")
                first_txn_at = parse_date(row.get("first_txn_date") or "")
                latest_txn_at = parse_date(row.get("latest_txn_date") or "")

                member = Member(
                    id=member_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    status=status,
                    memberships_raw=memberships_raw,
                    registered_at=registered_at,
                    first_txn_at=first_txn_at,
                    latest_txn_at=latest_txn_at,
                    country=country,
                    state_province=state,
                    city=city,
                )
                db.add(member)

                display_name_parts = [p for p in [first_name, last_name] if p]
                display_name = " ".join(display_name_parts) if display_name_parts else "Member"

                # Derive member_since_year from first transaction or registration
                ts = first_txn_at or registered_at
                member_since_year = ts.year if ts else None

                location_display = build_location_display(city, state, country)

                profile = DirectoryProfile(
                    id=member_id,
                    member_id=member_id,
                    display_name=display_name,
                    entry_type="individual",
                    role=None,
                    organization=None,
                    city=city,
                    state_province=state,
                    country=country,
                    location_display=location_display,
                    website_url=None,
                    tags_csv=None,
                    member_since_year=member_since_year,
                    visibility_public=True,
                )
                db.add(profile)

            db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    main()

