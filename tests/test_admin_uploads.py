"""Admin profile image uploads (Task 9)."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api import config
from api.db import get_db
from api.main import create_app
from api.models import DirectoryProfile


@pytest.fixture
def client_admin(tmp_path, monkeypatch, test_engine, test_session_local):
    import api.db as db_mod
    import api.main as main_mod

    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_session_local)
    monkeypatch.setattr(main_mod, "engine", test_engine)

    monkeypatch.setenv("DATA_SOURCE", "sqlite")
    monkeypatch.setattr(config, "ADMIN_API_KEY", "test-admin-secret")
    uploads = tmp_path / "uploads"
    monkeypatch.setattr(config, "UPLOADS_ROOT", str(uploads))

    app = main_mod.create_app()

    def _get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_admin_logo_requires_key(client_admin, db_session: Session):
    seed_profile(db_session)
    r = client_admin.post(
        "/api/v1/admin/profiles/103/logo",
        files={"file": ("logo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
    )
    assert r.status_code == 401


def test_admin_logo_uploads_and_updates_db(client_admin, db_session: Session):
    seed_profile(db_session)
    r = client_admin.post(
        "/api/v1/admin/profiles/103/logo",
        headers={"X-Admin-API-Key": "test-admin-secret"},
        files={"file": ("logo.png", io.BytesIO(b"\x89PNG\r\n\x1a\n"), "image/png")},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["logo_url"] == "/uploads/profiles/103/logo.png"
    db_session.expire_all()
    p = db_session.get(DirectoryProfile, 103)
    assert p is not None
    assert p.logo_url == "/uploads/profiles/103/logo.png"


def test_admin_gallery_appends_paths(client_admin, db_session: Session):
    seed_profile(db_session)
    r = client_admin.post(
        "/api/v1/admin/profiles/103/gallery",
        headers={"X-Admin-API-Key": "test-admin-secret"},
        files=[
            ("files", ("a.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["added"]) == 1
    assert body["gallery"] == ["/uploads/profiles/103/gallery/001.jpg"]


def seed_profile(db: Session) -> None:
    """Minimal profile row for admin id 103 (matches public tests pattern)."""
    if db.get(DirectoryProfile, 103):
        return
    db.add(
        DirectoryProfile(
            id=103,
            member_id=103,
            display_name="Test Biz",
            entry_type="business",
            role="Vendor",
            visibility_public=True,
            opted_in=True,
        )
    )
    db.commit()
