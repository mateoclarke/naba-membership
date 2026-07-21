"""Connect / outreach form (Task 10)."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from api.connect_logic import reset_rate_limits_for_tests
from api.models import ConnectMessage


REF = {"Referer": "http://localhost:4321/directory/business/test"}


@pytest.fixture(autouse=True)
def _reset_connect_rate_limits():
    reset_rate_limits_for_tests()
    yield
    reset_rate_limits_for_tests()


def _payload(
    recipient_id: int = 103,
    name: str = "Jane Doe",
    email: str = "jane@example.com",
    message: str = "Hello, I would like to connect about workshops.",
    website: str = "",
):
    return {
        "recipient_id": recipient_id,
        "sender_name": name,
        "sender_email": email,
        "message": message,
        "website": website,
    }


def test_connect_submits_201(client_with_data):
    r = client_with_data.post(
        "/api/v1/public/connect",
        json=_payload(),
        headers=REF,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert "review" in data["message"].lower()


def test_connect_requires_referer_when_enabled(client_with_data, monkeypatch):
    import api.config as cfg

    monkeypatch.setattr(cfg, "CONNECT_REQUIRE_REFERER", True)
    r = client_with_data.post("/api/v1/public/connect", json=_payload())
    assert r.status_code == 403


def test_connect_rejects_without_allow_connect(client_with_data):
    r = client_with_data.post(
        "/api/v1/public/connect",
        json=_payload(recipient_id=101),
        headers=REF,
    )
    assert r.status_code == 400


def test_connect_rejects_short_message(client_with_data):
    r = client_with_data.post(
        "/api/v1/public/connect",
        json=_payload(message="short"),
        headers=REF,
    )
    assert r.status_code == 400


def test_connect_honeypot_stores_spam(client_with_data, db_session):
    r = client_with_data.post(
        "/api/v1/public/connect",
        json=_payload(website="http://spam.example"),
        headers=REF,
    )
    assert r.status_code == 201
    db_session.expire_all()
    row = db_session.scalars(
        select(ConnectMessage).order_by(ConnectMessage.id.desc()).limit(1)
    ).first()
    assert row is not None
    assert row.status == "spam"


def test_connect_rate_limit(client_with_data):
    for _ in range(5):
        r = client_with_data.post(
            "/api/v1/public/connect",
            json=_payload(),
            headers=REF,
        )
        assert r.status_code == 201
    r6 = client_with_data.post(
        "/api/v1/public/connect",
        json=_payload(),
        headers=REF,
    )
    assert r6.status_code == 429


def test_admin_list_connect_requires_key(client_with_data):
    r = client_with_data.get("/api/v1/admin/connect/")
    # No ADMIN_API_KEY → 503; wrong key → 401
    assert r.status_code in (401, 503)


def test_admin_list_and_review(client_with_data, monkeypatch):
    import api.config as cfg

    monkeypatch.setattr(cfg, "ADMIN_API_KEY", "adm-secret")
    client_with_data.post(
        "/api/v1/public/connect",
        json=_payload(message="Enough chars here for validation."),
        headers=REF,
    )
    r = client_with_data.get(
        "/api/v1/admin/connect/",
        headers={"X-Admin-API-Key": "adm-secret"},
    )
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    mid = items[0]["id"]
    r2 = client_with_data.put(
        f"/api/v1/admin/connect/{mid}",
        json={"status": "approved"},
        headers={"X-Admin-API-Key": "adm-secret"},
    )
    assert r2.status_code == 200
    assert r2.json()["status"] == "approved"
    assert r2.json()["reviewed_at"] is not None
