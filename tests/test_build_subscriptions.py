"""Unit tests for MemberPress → subscription rows used on /me profile."""

from __future__ import annotations

from scripts.sync_from_wordpress import build_subscriptions


def test_build_subscriptions_from_active_sub_and_txn():
    data = {
        "active_txn_count": "1",
        "expired_txn_count": "0",
        "active_memberships": [
            {"id": 1361, "title": "PROFESSIONAL MEMBERSHIP", "period": "1", "period_type": "years"}
        ],
        "recent_subscriptions": [
            {
                "id": "90",
                "membership": "1361",
                "status": "active",
                "period": "1",
                "period_type": "years",
                "created_at": "2026-06-22 22:45:43",
            }
        ],
        "recent_transactions": [
            {
                "id": "2356",
                "membership": "1361",
                "subscription": "90",
                "status": "complete",
                "expires_at": "2027-06-22 23:59:59",
                "created_at": "2026-06-22 22:45:47",
                "member": "617",
            }
        ],
        "latest_txn": {
            "id": "2356",
            "membership": "1361",
            "subscription": "90",
            "status": "complete",
            "expires_at": "2027-06-22 23:59:59",
            "created_at": "2026-06-22 22:45:47",
            "member": "617",
        },
    }
    items = build_subscriptions(data)
    assert len(items) == 1
    assert items[0]["title"] == "PROFESSIONAL MEMBERSHIP"
    assert items[0]["status"] == "active"
    assert items[0]["expires_at"] == "2027-06-22T23:59:59"
    assert items[0]["is_lifetime"] is False
    assert items[0]["subscription_id"] == 90
    assert items[0]["membership_id"] == 1361


def test_build_subscriptions_lifetime_expires():
    data = {
        "active_txn_count": "1",
        "active_memberships": [{"id": 10, "title": "LIFETIME"}],
        "recent_subscriptions": [],
        "recent_transactions": [
            {
                "id": "1",
                "membership": "10",
                "subscription": "0",
                "status": "complete",
                "expires_at": "0000-00-00 00:00:00",
                "member": "1",
            }
        ],
        "latest_txn": {
            "id": "1",
            "membership": "10",
            "member": "1",
            "status": "complete",
            "expires_at": "0000-00-00 00:00:00",
        },
    }
    items = build_subscriptions(data)
    assert len(items) == 1
    assert items[0]["status"] == "active"
    assert items[0]["is_lifetime"] is True
    assert items[0]["expires_at"] is None


def test_build_subscriptions_falls_back_to_latest_txn_when_expired():
    data = {
        "active_txn_count": "0",
        "expired_txn_count": "1",
        "active_memberships": [],
        "recent_subscriptions": [],
        "recent_transactions": [],
        "latest_txn": {
            "id": "99",
            "membership": "1363",
            "subscription": "0",
            "status": "complete",
            "expires_at": "2024-01-01 23:59:59",
            "created_at": "2023-01-01 12:00:00",
            "member": "5",
        },
    }
    items = build_subscriptions(data)
    assert len(items) == 1
    assert items[0]["status"] == "expired"
    assert items[0]["expires_at"] == "2024-01-01T23:59:59"
