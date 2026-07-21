"""Sync script idempotency against an isolated DB (Task 6 §5)."""

from __future__ import annotations

import importlib

from sqlalchemy import select, func

from api.models import DirectoryProfile, Member


def _sample_wp_member(
    wp_id: int,
    *,
    first: str = "Sync",
    last: str = "Test",
    city: str = "Denver",
    state: str = "CO",
    country: str = "US",
) -> dict:
    ts = "2020-06-15 10:00:00"
    return {
        "id": wp_id,
        "first_name": first,
        "last_name": last,
        "display_name": f"{first} {last}",
        "email": f"sync{wp_id}@example.com",
        "registered_at": ts,
        "active_txn_count": 1,
        "expired_txn_count": 0,
        "active_memberships": [{"title": "Individual Membership"}],
        "address": {
            "mepr-address-city": city,
            "mepr-address-state": state,
            "mepr-address-country": country,
        },
        "profile": {},
        "url": "",
        "first_txn": {"id": 1, "member": wp_id, "created_at": ts},
        "latest_txn": {"id": 1, "member": wp_id, "created_at": ts},
    }


def test_sync_main_twice_same_counts(monkeypatch, test_engine, test_session_local):
    import api.db as db_mod
    import api.main as main_mod

    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_session_local)
    monkeypatch.setattr(main_mod, "engine", test_engine)

    monkeypatch.setenv("WP_API_URL", "https://example.test/wp-json/mp/v1")
    monkeypatch.setenv("WP_API_KEY", "dummy")

    payload = [_sample_wp_member(501), _sample_wp_member(502, first="Other")]

    import scripts.sync_from_wordpress as sync

    importlib.reload(sync)
    monkeypatch.setattr(sync, "fetch_all_members", lambda url, key: list(payload))

    sync.main()
    sync.main()

    db = test_session_local()
    try:
        n_members = db.scalar(select(func.count()).select_from(Member))
        n_profiles = db.scalar(select(func.count()).select_from(DirectoryProfile))
        assert n_members == 2
        assert n_profiles == 2
    finally:
        db.close()
