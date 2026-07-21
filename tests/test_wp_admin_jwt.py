"""WP-admin member JWT unlocks admin APIs and public show_all."""

from __future__ import annotations

import pytest

from api import config
from api.auth_wp import WpAuthResult
from api.security import issue_member_access_token


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setattr(
        config,
        "AUTH_JWT_SECRET",
        "unit-test-jwt-secret-32bytes-min!!",
    )
    monkeypatch.setattr(config, "ADMIN_API_KEY", "")
    monkeypatch.setattr(config, "WP_JWT_TOKEN_URL", "https://example.com/jwt")
    monkeypatch.setattr(config, "WP_REST_USER_ME_URL", "https://example.com/me")


async def fake_wp_admin(_username: str, _password: str) -> WpAuthResult:
    return WpAuthResult(user_id=101, roles=["administrator"])


async def fake_wp_member(_username: str, _password: str) -> WpAuthResult:
    return WpAuthResult(user_id=101, roles=["subscriber"])


def test_admin_list_requires_auth_when_unconfigured(client_with_data, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "")
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "")
    r = client_with_data.get("/api/v1/admin/profiles/")
    assert r.status_code == 503


def test_admin_list_401_without_token_when_jwt_configured(client_with_data, auth_env):
    r = client_with_data.get("/api/v1/admin/profiles/")
    assert r.status_code == 401


def test_admin_member_jwt_can_list_and_update(client_with_data, auth_env, monkeypatch):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_admin)
    login = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret"},
    )
    assert login.status_code == 200
    assert login.json()["is_admin"] is True
    token = login.json()["access_token"]

    listed = client_with_data.get(
        "/api/v1/admin/profiles/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert 104 in ids  # non-opted-in visible to admin

    updated = client_with_data.put(
        "/api/v1/admin/profiles/104",
        headers={"Authorization": f"Bearer {token}"},
        json={"opted_in": True, "badges_csv": "board", "bio": "Admin edit"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["opted_in"] is True
    assert body["badges_csv"] == "board"
    assert body["bio"] == "Admin edit"


def test_non_admin_member_jwt_rejected_by_admin_routes(client_with_data, auth_env, monkeypatch):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_member)
    token = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret"},
    ).json()["access_token"]
    assert client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret"},
    ).json()["is_admin"] is False

    r = client_with_data.get(
        "/api/v1/admin/profiles/",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


def test_show_all_requires_admin_jwt(client_with_data, auth_env):
    # Without auth, public list is businesses-only (no hidden individual 104)
    public = client_with_data.get("/api/v1/public/members/?page_size=500")
    assert public.status_code == 200
    public_ids = {i["id"] for i in public.json()["items"]}
    assert 104 not in public_ids
    assert all(i["entry_type"] == "business" for i in public.json()["items"])

    admin_token, _ = issue_member_access_token(101, is_admin=True)
    shown = client_with_data.get(
        "/api/v1/public/members/?page_size=500&show_all=true",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert shown.status_code == 200
    shown_ids = {i["id"] for i in shown.json()["items"]}
    assert 104 in shown_ids

    member_token, _ = issue_member_access_token(101, is_admin=False, membership_status="active")
    denied = client_with_data.get(
        "/api/v1/public/members/?page_size=500&show_all=true",
        headers={"Authorization": f"Bearer {member_token}"},
    )
    assert denied.status_code == 200
    denied_ids = {i["id"] for i in denied.json()["items"]}
    assert 104 not in denied_ids
