"""
Optional full-stack checks (Task 6 §1).

Requires for WordPress total test:
  RUN_INTEGRATION_E2E=1
  WP_API_URL, WP_API_KEY

Optional public API smoke (running uvicorn):
  MEMBERSHIP_E2E_API_URL=http://localhost:8000
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = pytest.mark.integration


def _skip_wordpress_reason() -> str | None:
    if os.environ.get("RUN_INTEGRATION_E2E", "").strip() != "1":
        return "set RUN_INTEGRATION_E2E=1 to run WordPress integration tests"
    if not os.environ.get("WP_API_URL") or not os.environ.get("WP_API_KEY"):
        return "WP_API_URL and WP_API_KEY required"
    return None


def _skip_api_smoke_reason() -> str | None:
    base = _skip_wordpress_reason()
    if base:
        return base
    if not os.environ.get("MEMBERSHIP_E2E_API_URL", "").strip():
        return "MEMBERSHIP_E2E_API_URL not set (e.g. http://localhost:8000)"
    return None


@pytest.mark.skipif(
    _skip_wordpress_reason() is not None,
    reason=_skip_wordpress_reason() or "integration off",
)
def test_wordpress_x_wp_total_matches_full_fetch():
    """MemberPress list total header should match paginated fetch length."""
    base = os.environ["WP_API_URL"].rstrip("/")
    key = os.environ["WP_API_KEY"]
    r = requests.get(
        f"{base}/members",
        params={"per_page": 1, "page": 1},
        headers={"MEMBERPRESS-API-KEY": key},
        timeout=60,
    )
    r.raise_for_status()
    total_hdr = r.headers.get("X-WP-Total")
    assert total_hdr is not None, "Expected X-WP-Total header from MemberPress API"
    wp_total = int(total_hdr)

    from scripts.sync_from_wordpress import fetch_all_members

    all_rows = fetch_all_members(base, key)
    assert len(all_rows) == wp_total


@pytest.mark.skipif(
    _skip_api_smoke_reason() is not None,
    reason=_skip_api_smoke_reason() or "integration off",
)
def test_public_api_reachable_and_paginated():
    """Smoke: running FastAPI returns JSON with total and items."""
    api_base = os.environ["MEMBERSHIP_E2E_API_URL"].rstrip("/")
    r = requests.get(
        f"{api_base}/api/v1/public/members/",
        params={"page_size": 1},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    assert "total" in data and "items" in data
    assert isinstance(data["items"], list)
