"""Member login + /me/profile (Task 12)."""

from __future__ import annotations

import pytest

from api import config
from api.auth_wp import WpAuthResult


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setattr(
        config,
        "AUTH_JWT_SECRET",
        "unit-test-jwt-secret-32bytes-min!!",
    )
    monkeypatch.setattr(config, "WP_JWT_TOKEN_URL", "https://example.com/jwt")
    monkeypatch.setattr(config, "WP_REST_USER_ME_URL", "https://example.com/me")


async def fake_wp_user(_username: str, _password: str) -> WpAuthResult:
    return WpAuthResult(user_id=101, roles=[])


async def fake_wp_admin(_username: str, _password: str) -> WpAuthResult:
    return WpAuthResult(user_id=101, roles=["administrator"])


def test_auth_login_503_when_wp_not_configured(client_with_data, monkeypatch):
    monkeypatch.delenv("WP_SITE_URL", raising=False)
    monkeypatch.setattr(config, "WP_JWT_TOKEN_URL", "")
    monkeypatch.setattr(config, "WP_REST_USER_ME_URL", "")
    monkeypatch.setattr(config, "WP_SITE_URL", "")
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "x")
    r = client_with_data.post("/api/v1/auth/login", json={"username": "a", "password": "b"})
    assert r.status_code == 503


def test_auth_login_and_me_profile(client_with_data, auth_env, monkeypatch):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_user)

    r = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert body["expires_in"] > 0
    assert body["is_admin"] is False
    assert body.get("membership_status") == "active"

    token = body["access_token"]
    me = client_with_data.get(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["display_name"] == "Alice Smith"
    assert me.json()["email"] == "alice@example.com"
    assert me.json()["membership_status"] == "active"
    subs = me.json().get("subscriptions") or []
    assert len(subs) == 1
    assert subs[0]["title"] == "PROFESSIONAL MEMBERSHIP"
    assert subs[0]["status"] == "active"
    assert subs[0]["expires_at"] == "2027-06-22T23:59:59"
    assert subs[0]["is_lifetime"] is False


def test_auth_login_is_admin_for_wp_administrator(client_with_data, auth_env, monkeypatch):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_admin)
    r = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret"},
    )
    assert r.status_code == 200
    assert r.json()["is_admin"] is True


def test_me_profile_requires_token(client_with_data):
    r = client_with_data.get("/api/v1/me/profile")
    assert r.status_code == 401


def test_me_put_logo_url(client_with_data, auth_env, monkeypatch):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_user)
    token = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "a", "password": "b"},
    ).json()["access_token"]

    ok = client_with_data.put(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"logo_url": "https://example.com/logo.png"},
    )
    assert ok.status_code == 200
    assert ok.json()["logo_url"] == "https://example.com/logo.png"

    bad = client_with_data.put(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"logo_url": "javascript:alert(1)"},
    )
    assert bad.status_code == 422

    cleared = client_with_data.put(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"logo_url": ""},
    )
    assert cleared.status_code == 200
    assert cleared.json()["logo_url"] in (None, "")


def test_me_put_scoped_fields(client_with_data, auth_env, monkeypatch):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_user)
    token = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "a", "password": "b"},
    ).json()["access_token"]

    r = client_with_data.put(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"bio": "Self-service bio", "organization": "My Org"},
    )
    assert r.status_code == 200
    assert r.json()["bio"] == "Self-service bio"
    assert r.json()["organization"] == "My Org"


def test_me_businesses_list_and_update(client_with_data, auth_env, monkeypatch):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_user)
    token = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "a", "password": "b"},
    ).json()["access_token"]

    r_list = client_with_data.get(
        "/api/v1/me/businesses",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_list.status_code == 200
    assert r_list.json()[0]["business_id"] == 103

    r_get = client_with_data.get(
        "/api/v1/me/businesses/103/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_get.status_code == 200
    assert r_get.json()["display_name"] == "Canadian Business Inc"

    r_put = client_with_data.put(
        "/api/v1/me/businesses/103/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"bio": "Updated by linked member"},
    )
    assert r_put.status_code == 200
    assert r_put.json()["bio"] == "Updated by linked member"


def test_me_put_categories_materials_normalized_and_validated(
    client_with_data, auth_env, monkeypatch
):
    monkeypatch.setattr("api.routers_auth.authenticate_wp_user", fake_wp_user)
    token = client_with_data.post(
        "/api/v1/auth/login",
        json={"username": "a", "password": "b"},
    ).json()["access_token"]

    ok = client_with_data.put(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "categories_csv": "  Professional, educator,professional ",
            "materials_csv": "Adobe, cob, adobe",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["categories_csv"] == "professional,educator"
    assert ok.json()["materials_csv"] == "adobe,cob"

    bad = client_with_data.put(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"categories_csv": "professional,unknown-category"},
    )
    assert bad.status_code == 422
