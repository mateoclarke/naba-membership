"""Member map requires active membership (or WP admin JWT)."""

from __future__ import annotations

from api import config
from api.models import DirectoryProfile
from api.security import issue_member_access_token


def _headers(monkeypatch, *, status: str = "active", is_admin: bool = False):
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "unit-test-jwt-secret-32bytes-min!!")
    token, _ = issue_member_access_token(
        101, membership_status=status, is_admin=is_admin
    )
    return {"Authorization": f"Bearer {token}"}


def test_map_requires_auth(client_with_data):
    r = client_with_data.get("/api/v1/public/members/map")
    assert r.status_code == 401


def test_map_rejects_inactive_member(client_with_data, monkeypatch):
    headers = _headers(monkeypatch, status="expired")
    r = client_with_data.get("/api/v1/public/members/map", headers=headers)
    assert r.status_code == 401


def test_map_allows_active_member(client_with_data, monkeypatch, db_session):
    profile = db_session.get(DirectoryProfile, 101)
    assert profile is not None
    profile.latitude = 40.0
    profile.longitude = -105.0
    db_session.commit()

    headers = _headers(monkeypatch, status="active")
    r = client_with_data.get("/api/v1/public/members/map", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == 101 for i in items)


def test_map_allows_admin_even_if_inactive(client_with_data, monkeypatch):
    headers = _headers(monkeypatch, status="none", is_admin=True)
    r = client_with_data.get("/api/v1/public/members/map", headers=headers)
    assert r.status_code == 200
