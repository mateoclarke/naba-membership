"""Sync script fails with clear errors when WP is unreachable or rejects auth."""

from __future__ import annotations

import importlib

import pytest
import requests


def test_sync_missing_env_exits_with_message(monkeypatch, test_engine, test_session_local):
    import api.db as db_mod
    import api.main as main_mod

    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_session_local)
    monkeypatch.setattr(main_mod, "engine", test_engine)

    monkeypatch.delenv("WP_API_URL", raising=False)
    monkeypatch.delenv("WP_API_KEY", raising=False)

    import scripts.sync_from_wordpress as sync

    importlib.reload(sync)
    with pytest.raises(SystemExit) as excinfo:
        sync.main()
    msg = str(excinfo.value)
    assert "WP_API_URL" in msg and "WP_API_KEY" in msg


def test_sync_http_401_exits_with_clear_message(monkeypatch, test_engine, test_session_local):
    import api.db as db_mod
    import api.main as main_mod

    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_session_local)
    monkeypatch.setattr(main_mod, "engine", test_engine)

    monkeypatch.setenv("WP_API_URL", "https://example.test/wp-json/mp/v1")
    monkeypatch.setenv("WP_API_KEY", "invalid-key")

    import scripts.sync_from_wordpress as sync

    importlib.reload(sync)

    def fake_get(*_a, **_k):
        r = requests.Response()
        r.status_code = 401
        r.url = "https://example.test/wp-json/mp/v1/members"
        r._content = b'{"code":"invalid"}'
        raise requests.HTTPError(response=r)

    monkeypatch.setattr(sync.requests, "get", fake_get)

    with pytest.raises(SystemExit) as excinfo:
        sync.main()
    msg = str(excinfo.value)
    assert "401" in msg
    assert "WP_API_KEY" in msg or "MEMBERPRESS" in msg
