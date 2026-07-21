from __future__ import annotations

import pytest

from api import config


@pytest.fixture
def client_admin(client_with_data, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_API_KEY", "test-admin-secret")
    yield client_with_data


def test_admin_business_member_endpoints(client_admin):
    headers = {"Authorization": "Bearer test-admin-secret"}

    r_list = client_admin.get("/api/v1/admin/business-members/", headers=headers)
    assert r_list.status_code == 200
    assert r_list.json()["total"] >= 1
    assert "member_display_name" in r_list.json()["items"][0]

    r_create = client_admin.post(
        "/api/v1/admin/business-members/",
        headers=headers,
        json={
            "business_profile_id": 103,
            "member_profile_id": 104,
            "role_in_business": "Support",
            "can_edit": False,
        },
    )
    assert r_create.status_code == 200
    link_id = r_create.json()["id"]
    assert r_create.json()["can_edit"] is False

    # Upsert updates can_edit / role
    r_upsert = client_admin.post(
        "/api/v1/admin/business-members/",
        headers=headers,
        json={
            "business_profile_id": 103,
            "member_profile_id": 104,
            "role_in_business": "Editor",
            "can_edit": True,
        },
    )
    assert r_upsert.status_code == 200
    assert r_upsert.json()["id"] == link_id
    assert r_upsert.json()["can_edit"] is True
    assert r_upsert.json()["role_in_business"] == "Editor"

    r_patch = client_admin.patch(
        f"/api/v1/admin/business-members/{link_id}",
        headers=headers,
        json={"can_edit": False, "role_in_business": "Support"},
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["can_edit"] is False
    assert r_patch.json()["role_in_business"] == "Support"

    r_delete = client_admin.delete(f"/api/v1/admin/business-members/{link_id}", headers=headers)
    assert r_delete.status_code == 200


def test_admin_business_member_accepts_organization(client_admin, db_session):
    from api.models import DirectoryProfile

    headers = {"Authorization": "Bearer test-admin-secret"}
    org = db_session.get(DirectoryProfile, 103)
    assert org is not None
    org.entry_type = "organization"
    db_session.add(org)
    db_session.commit()

    r = client_admin.post(
        "/api/v1/admin/business-members/",
        headers=headers,
        json={
            "business_profile_id": 103,
            "member_profile_id": 101,
            "role_in_business": "Staff",
            "can_edit": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["business_profile_id"] == 103
