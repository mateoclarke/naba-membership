"""
Shared fixtures: isolated SQLite DB + FastAPI TestClient.

Patches api.db (and api.main.engine used by create_app) so tests never touch data/membership.db.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.db import Base, get_db
from api.main import create_app
from api.models import BusinessMember, DirectoryProfile, Member


@pytest.fixture
def test_engine(tmp_path):
    path = tmp_path / "test_membership.db"
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def test_session_local(test_engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture
def db_session(test_session_local) -> Session:
    db = test_session_local()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(monkeypatch, test_engine, test_session_local):
    import api.db as db_mod
    import api.main as main_mod

    monkeypatch.setattr(db_mod, "engine", test_engine)
    monkeypatch.setattr(db_mod, "SessionLocal", test_session_local)
    monkeypatch.setattr(main_mod, "engine", test_engine)

    monkeypatch.setenv("DATA_SOURCE", "sqlite")

    app = main_mod.create_app()

    def _get_db():
        db = test_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db

    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def seed_minimal_public_profiles(db: Session) -> None:
    """Three public profiles + one hidden, for filter and PII tests."""

    m1 = Member(
        id=101,
        first_name="Alice",
        last_name="Smith",
        email="alice@example.com",
        status="active",
        city="Boulder",
        state_province="CO",
        country="US",
        subscriptions_json=(
            '[{"membership_id":1361,"subscription_id":90,"title":"PROFESSIONAL MEMBERSHIP",'
            '"status":"active","period":"1","period_type":"years",'
            '"created_at":"2026-06-22T22:45:43","expires_at":"2027-06-22T23:59:59",'
            '"is_lifetime":false}]'
        ),
    )
    m2 = Member(
        id=102,
        first_name="Bob",
        last_name="Jones",
        email="bob@example.com",
        status="active",
        city="Los Angeles",
        state_province="CA",
        country="US",
    )
    m3 = Member(
        id=103,
        first_name="Corp",
        last_name="Org",
        email="corp@example.com",
        status="active",
        city="Toronto",
        state_province="ON",
        country="CA",
    )
    m4 = Member(
        id=104,
        first_name="Hidden",
        last_name="User",
        email="hidden@example.com",
        status="active",
    )
    db.add_all([m1, m2, m3, m4])
    db.flush()

    db.add_all(
        [
            DirectoryProfile(
                id=101,
                member_id=101,
                display_name="Alice Smith",
                entry_type="individual",
                role="Individual",
                organization=None,
                city="Boulder",
                state_province="CO",
                country="US",
                location_display="Boulder, CO (US)",
                website_url="https://alice.example",
                tags_csv="individual",
                member_since_year=2022,
                visibility_public=True,
                opted_in=True,
            ),
            DirectoryProfile(
                id=102,
                member_id=102,
                display_name="Bob Jones",
                entry_type="organization",
                role="Professional",
                organization="NaBA Test Org",
                city="Los Angeles",
                state_province="CA",
                country="US",
                location_display="Los Angeles, CA (US)",
                website_url=None,
                tags_csv="professional",
                member_since_year=2021,
                visibility_public=True,
                opted_in=True,
            ),
            DirectoryProfile(
                id=103,
                member_id=103,
                display_name="Canadian Business Inc",
                entry_type="business",
                role="Vendor",
                organization="Canadian Business Inc",
                city="Toronto",
                state_province="ON",
                country="CA",
                location_display="Toronto, ON (CA)",
                website_url="https://biz.example",
                tags_csv="vendor",
                member_since_year=2020,
                visibility_public=True,
                opted_in=True,
                slug="canadian-biz",
                bio="Natural building supplies and workshops.",
                gallery_json='["/uploads/profiles/103/gallery/001.jpg"]',
                phone="555-0100",
                social_json='{"facebook": "https://facebook.com/example"}',
                services_csv="design, workshops",
                regions_csv="Southwest US, CA",
                allow_connect=True,
            ),
            DirectoryProfile(
                id=104,
                member_id=104,
                display_name="Hidden User",
                entry_type="individual",
                role="Member",
                visibility_public=False,
            ),
        ]
    )
    db.add(
        BusinessMember(
            business_profile_id=103,
            member_profile_id=101,
            role_in_business="Owner",
            can_edit=True,
        )
    )
    db.commit()


@pytest.fixture
def client_with_data(client, db_session):
    seed_minimal_public_profiles(db_session)
    return client
