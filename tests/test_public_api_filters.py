"""Search, filters, and pagination (Task 6 §4)."""

from __future__ import annotations

from api import config
from api.security import issue_member_access_token


def _active_headers(client_with_data, monkeypatch):
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "unit-test-jwt-secret-32bytes-min!!")
    token, _ = issue_member_access_token(101, membership_status="active")
    return {"Authorization": f"Bearer {token}"}


def test_anonymous_public_list_is_businesses_only(client_with_data):
    r = client_with_data.get("/api/v1/public/members/", params={"page_size": 100})
    assert r.status_code == 200
    types = {i["entry_type"] for i in r.json()["items"]}
    assert types == {"business"}


def test_anonymous_cannot_request_individuals(client_with_data):
    r = client_with_data.get(
        "/api/v1/public/members/", params={"entry_type": "individual"}
    )
    assert r.status_code == 401


def test_search_by_name_q(client_with_data, monkeypatch):
    headers = _active_headers(client_with_data, monkeypatch)
    r = client_with_data.get(
        "/api/v1/public/members/", params={"q": "smith"}, headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["display_name"] == "Alice Smith"


def test_filter_country(client_with_data, monkeypatch):
    headers = _active_headers(client_with_data, monkeypatch)
    r = client_with_data.get(
        "/api/v1/public/members/", params={"country": "US"}, headers=headers
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    countries = {i["country"] for i in data["items"]}
    assert countries == {"US"}


def test_filter_state_province(client_with_data, monkeypatch):
    headers = _active_headers(client_with_data, monkeypatch)
    r = client_with_data.get(
        "/api/v1/public/members/",
        params={"state_province": "CO"},
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["display_name"] == "Alice Smith"


def test_filter_entry_type(client_with_data, monkeypatch):
    headers = _active_headers(client_with_data, monkeypatch)
    r = client_with_data.get(
        "/api/v1/public/members/",
        params={"entry_type": "individual"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["total"] == 1

    r2 = client_with_data.get(
        "/api/v1/public/members/", params={"entry_type": "business"}
    )
    assert r2.status_code == 200
    assert r2.json()["total"] == 1


def test_pagination(client_with_data, monkeypatch):
    headers = _active_headers(client_with_data, monkeypatch)
    r = client_with_data.get(
        "/api/v1/public/members/",
        params={"page": 1, "page_size": 2},
        headers=headers,
    )
    assert r.status_code == 200
    d1 = r.json()
    assert d1["page"] == 1
    assert d1["page_size"] == 2
    assert d1["total"] == 3
    assert len(d1["items"]) == 2

    r2 = client_with_data.get(
        "/api/v1/public/members/",
        params={"page": 2, "page_size": 2},
        headers=headers,
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["page"] == 2
    assert len(d2["items"]) == 1


def test_health_includes_data_source(client):
    r = client.get("/health")
    assert r.status_code == 200
    h = r.json()
    assert h["status"] == "ok"
    assert h["data_source"] == "sqlite"
