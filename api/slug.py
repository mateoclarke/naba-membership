"""URL slugs for directory profiles (custom or computed name-id)."""

from __future__ import annotations

from typing import Optional

import re

from .models import DirectoryProfile


def slugify(text: str) -> str:
    s = (text or "").lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s or "member"


def effective_slug(profile: DirectoryProfile) -> str:
    """Public canonical path segment: custom slug, else `{slugify(display_name)}-{id}`."""
    raw = getattr(profile, "slug", None)
    if raw and str(raw).strip():
        return str(raw).strip()
    return f"{slugify(profile.display_name)}-{profile.id}"


def parse_trailing_profile_id(slug: str) -> Optional[int]:
    """If slug ends with `-{digits}`, return that id (for computed slugs)."""
    m = re.search(r"-(\d+)$", slug.strip())
    if not m:
        return None
    return int(m.group(1))
