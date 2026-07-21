"""Admin profile list/detail/update (Task 11)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from api import config
from api.models import DirectoryProfile


@pytest.fixture
def client_admin(client_with_data, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "test-admin-secret")
    yield client_with_data


def test_admin_list_requires_auth(client_with_data, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "")
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "")
    r = client_with_data.get("/api/v1/admin/profiles/")
    # No ADMIN_API_KEY and no AUTH_JWT_SECRET → 503
    assert r.status_code == 503


def test_admin_list_includes_non_opted_in(client_admin, db_session: Session):
    r = client_admin.get(
        "/api/v1/admin/profiles/",
        headers={"Authorization": "Bearer test-admin-secret"},
    )
    assert r.status_code == 200
    data = r.json()
    ids = {item["id"] for item in data["items"]}
    assert 104 in ids
    hidden = next(i for i in data["items"] if i["id"] == 104)
    assert hidden["opted_in"] is False


def test_admin_get_and_patch(client_admin, db_session: Session):
    r = client_admin.get(
        "/api/v1/admin/profiles/101",
        headers={"Authorization": "Bearer test-admin-secret"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"

    r2 = client_admin.put(
        "/api/v1/admin/profiles/101",
        headers={"Authorization": "Bearer test-admin-secret"},
        json={"bio": "Updated bio for admin test."},
    )
    assert r2.status_code == 200
    assert r2.json()["bio"] == "Updated bio for admin test."

    db_session.expire_all()
    p = db_session.get(DirectoryProfile, 101)
    assert p is not None
    assert p.bio == "Updated bio for admin test."


def test_admin_delete_gallery_index(client_admin, tmp_path, monkeypatch, db_session: Session):
    monkeypatch.setattr(config, "UPLOADS_ROOT", str(tmp_path))
    p = db_session.get(DirectoryProfile, 103)
    assert p is not None
    p.gallery_json = '["/uploads/profiles/103/gallery/001.jpg","/uploads/profiles/103/gallery/002.jpg"]'
    db_session.commit()

    gallery_dir = tmp_path / "profiles" / "103" / "gallery"
    gallery_dir.mkdir(parents=True)
    (gallery_dir / "001.jpg").write_bytes(b"a")
    (gallery_dir / "002.jpg").write_bytes(b"b")

    r = client_admin.delete(
        "/api/v1/admin/profiles/103/gallery/0",
        headers={"Authorization": "Bearer test-admin-secret"},
    )
    assert r.status_code == 200
    assert len(r.json()["gallery"]) == 1
    assert not (gallery_dir / "001.jpg").exists()
    assert (gallery_dir / "002.jpg").exists()


def test_admin_put_categories_materials_validated(client_admin):
    ok = client_admin.put(
        "/api/v1/admin/profiles/101",
        headers={"Authorization": "Bearer test-admin-secret"},
        json={
            "categories_csv": " vendor , professional, vendor ",
            "materials_csv": "Hempcrete, rammed earth, hempcrete",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["categories_csv"] == "vendor,professional"
    assert ok.json()["materials_csv"] == "hempcrete,rammed earth"

    bad = client_admin.put(
        "/api/v1/admin/profiles/101",
        headers={"Authorization": "Bearer test-admin-secret"},
        json={"materials_csv": "hempcrete,steel"},
    )
    assert bad.status_code == 422
