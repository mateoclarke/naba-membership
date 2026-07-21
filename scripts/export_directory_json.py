"""
Export directory data from the membership API to static JSON for Astro SSG builds.

Reads `PUBLIC_MEMBERSHIP_API_URL` from the environment (same as `.env.schema` /
repo root `.env`). Defaults to `http://localhost:8000` when unset.

Usage (from repo root):

    npx varlock run -- python -m scripts.export_directory_json

    # or, with a running API and env in the shell:
    python -m scripts.export_directory_json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

DEFAULT_BASE = "http://localhost:8000"
OUTPUT_REL = Path("astro-app/public/data/directoryEntries.json")
PAGE_SIZE = 500


def _api_base() -> str:
    return os.environ.get("PUBLIC_MEMBERSHIP_API_URL", DEFAULT_BASE).rstrip("/")


def fetch_all_items(base: str) -> list[dict[str, Any]]:
    """GET /api/v1/public/members/ with pagination until all rows are loaded."""
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        url = f"{base}/api/v1/public/members/"
        resp = requests.get(
            url,
            params={"page": page, "page_size": PAGE_SIZE},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        batch = data.get("items") or []
        items.extend(batch)
        total = int(data.get("total") or 0)
        if len(items) >= total or len(batch) < PAGE_SIZE:
            break
        page += 1
    return items


def map_item_to_entry(item: dict[str, Any]) -> dict[str, Any]:
    role = item.get("role") or "Member"
    loc = item.get("location_display") or ""
    org = item.get("organization")
    website = item.get("website_url")
    entry: dict[str, Any] = {
        "id": item["id"],
        "name": item["display_name"],
        "type": item["entry_type"],
        "role": role,
        "location": loc,
        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
        "badges": item.get("badges") if isinstance(item.get("badges"), list) else [],
    }
    if org:
        entry["org"] = org
    if website:
        entry["website"] = website
    if item.get("member_since_year") is not None:
        entry["member_since_year"] = item["member_since_year"]
    if item.get("logo_url"):
        entry["logo_url"] = item["logo_url"]
    if item.get("bio"):
        entry["bio"] = item["bio"]
    return entry


def export() -> int:
    base = _api_base()
    items = fetch_all_items(base)
    entries = [map_item_to_entry(i) for i in items]

    out = Path(__file__).resolve().parent.parent / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")

    print(f"Exported {len(entries)} entries from {base} to {out}")
    return len(entries)


def main() -> None:
    export()


if __name__ == "__main__":
    main()
