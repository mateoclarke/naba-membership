"""GET /api/v1/public/members/{id} full profile (Task 9)."""

from __future__ import annotations

from api import config
from api.security import issue_member_access_token


def _active_headers(monkeypatch):
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "unit-test-jwt-secret-32bytes-min!!")
    token, _ = issue_member_access_token(101, membership_status="active")
    return {"Authorization": f"Bearer {token}"}


def test_public_member_detail_returns_full_profile(client_with_data):
    r = client_with_data.get("/api/v1/public/members/103")
    assert r.status_code == 200
    data = r.json()
    assert data["slug"] == "canadian-biz"
    assert data["display_name"] == "Canadian Business Inc"
    assert data["bio"] == "Natural building supplies and workshops."
    assert data["gallery"] == ["/uploads/profiles/103/gallery/001.jpg"]
    assert data["phone"] == "555-0100"
    assert data["social"] == {"facebook": "https://facebook.com/example"}
    assert data["services"] == ["design", "workshops"]
    assert data["regions"] == ["Southwest US", "CA"]
    assert data["allow_connect"] is True
    assert data["team"] == [
        {
            "id": 101,
            "display_name": "Alice Smith",
            "role_in_business": "Owner",
            "slug": "alice-smith-101",
        }
    ]


def test_public_member_detail_not_listed_returns_404(client_with_data):
    r = client_with_data.get("/api/v1/public/members/104")
    assert r.status_code == 404


def test_public_member_detail_unknown_returns_404(client_with_data):
    r = client_with_data.get("/api/v1/public/members/99999")
    assert r.status_code == 404


def test_public_member_detail_by_custom_slug(client_with_data):
    r = client_with_data.get("/api/v1/public/members/by-slug/canadian-biz")
    assert r.status_code == 200
    assert r.json()["id"] == 103


def test_individual_detail_requires_active_member(client_with_data, monkeypatch):
    denied = client_with_data.get("/api/v1/public/members/101")
    assert denied.status_code == 401

    headers = _active_headers(monkeypatch)
    r = client_with_data.get("/api/v1/public/members/by-slug/alice-smith-101", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == 101
    assert r.json()["slug"] == "alice-smith-101"
    assert r.json()["affiliated_businesses"] == [
        {
            "id": 103,
            "display_name": "Canadian Business Inc",
            "role_in_business": "Owner",
            "slug": "canadian-biz",
        }
    ]


def test_public_member_by_slug_unknown_returns_404(client_with_data):
    r = client_with_data.get("/api/v1/public/members/by-slug/wrong-999")
    assert r.status_code == 404
