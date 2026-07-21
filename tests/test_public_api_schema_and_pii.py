"""
Public API must only expose directory-safe fields (Task 6 privacy verification).
"""

from __future__ import annotations

import re
from typing import Any

# Keys that must never appear in public JSON (substring match on key names, case-insensitive)
FORBIDDEN_KEY_SUBSTRINGS = (
    "email",
    "tel",
    "street",
    "address1",
    "address2",
    "zip",
    "postal",
    "mepr-address",
    "stripe",
    "login_count",
    "password",
    "secret",
    "txn",
    "transaction",
    "card",
    "ssn",
)

ALLOWED_TOP_LEVEL_KEYS = {"items", "page", "page_size", "total"}

ALLOWED_ITEM_KEYS = {
    "id",
    "display_name",
    "entry_type",
    "role",
    "organization",
    "city",
    "state_province",
    "country",
    "location_display",
    "website_url",
    "tags",
    "badges",
    "categories",
    "materials",
    "member_since_year",
    "logo_url",
    "slug",
    "latitude",
    "longitude",
    "membership_status",
    "last_active_date",
    "opted_in",
}


def collect_json_keys(obj: Any, out: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str):
                out.add(k)
            collect_json_keys(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_json_keys(v, out)


def test_public_members_response_has_no_forbidden_keys(client_with_data):
    r = client_with_data.get("/api/v1/public/members/?page_size=10")
    assert r.status_code == 200
    data = r.json()
    keys: set[str] = set()
    collect_json_keys(data, keys)
    lowered = {k.lower() for k in keys}
    for forbidden in FORBIDDEN_KEY_SUBSTRINGS:
        for k in lowered:
            assert forbidden not in k, f"unexpected key containing {forbidden!r}: {k!r}"


def test_public_members_top_level_and_item_keys(client_with_data):
    r = client_with_data.get("/api/v1/public/members/?page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == ALLOWED_TOP_LEVEL_KEYS
    # Anonymous callers only see businesses
    assert body["total"] == 1
    for item in body["items"]:
        assert set(item.keys()) == ALLOWED_ITEM_KEYS
        assert item["entry_type"] == "business"


def test_raw_json_string_has_no_email_like_leak(client_with_data):
    r = client_with_data.get("/api/v1/public/members/?page_size=10")
    text = r.text
    # Seeded internal emails must not appear in response
    assert "alice@example.com" not in text
    assert "bob@example.com" not in text
    # Loose check: no typical email pattern in payload
    assert not re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)


def test_hidden_profile_not_listed(client_with_data):
    r = client_with_data.get("/api/v1/public/members/?page_size=100")
    ids = {item["id"] for item in r.json()["items"]}
    assert 104 not in ids
