from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "membership.db"
DB_URL = f"sqlite:///{DB_PATH}"


class Base(DeclarativeBase):
    """SQLAlchemy base class."""


engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_directory_profile_slug_column(bind_engine) -> None:
    """SQLite: add optional slug column + unique index for existing DBs."""
    insp = inspect(bind_engine)
    if not insp.has_table("directory_profiles"):
        return
    cols = {c["name"] for c in insp.get_columns("directory_profiles")}
    if "slug" not in cols:
        with bind_engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE directory_profiles ADD COLUMN slug VARCHAR")
            )
        with bind_engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_directory_profiles_slug "
                    "ON directory_profiles (slug)"
                )
            )


def ensure_directory_profile_geocode_columns(bind_engine) -> None:
    """SQLite: add optional latitude/longitude columns for map markers."""
    insp = inspect(bind_engine)
    if not insp.has_table("directory_profiles"):
        return
    cols = {c["name"] for c in insp.get_columns("directory_profiles")}
    with bind_engine.begin() as conn:
        if "latitude" not in cols:
            conn.execute(
                text("ALTER TABLE directory_profiles ADD COLUMN latitude FLOAT")
            )
        if "longitude" not in cols:
            conn.execute(
                text("ALTER TABLE directory_profiles ADD COLUMN longitude FLOAT")
            )


def ensure_directory_profile_categories_materials_columns(bind_engine) -> None:
    """SQLite: add optional categories/materials enrichment columns."""
    insp = inspect(bind_engine)
    if not insp.has_table("directory_profiles"):
        return
    cols = {c["name"] for c in insp.get_columns("directory_profiles")}
    with bind_engine.begin() as conn:
        if "categories_csv" not in cols:
            conn.execute(
                text("ALTER TABLE directory_profiles ADD COLUMN categories_csv VARCHAR")
            )
        if "materials_csv" not in cols:
            conn.execute(
                text("ALTER TABLE directory_profiles ADD COLUMN materials_csv VARCHAR")
            )


def ensure_member_subscriptions_column(bind_engine) -> None:
    """SQLite: add subscriptions_json on members for profile membership UI."""
    insp = inspect(bind_engine)
    if not insp.has_table("members"):
        return
    cols = {c["name"] for c in insp.get_columns("members")}
    if "subscriptions_json" not in cols:
        with bind_engine.begin() as conn:
            conn.execute(text("ALTER TABLE members ADD COLUMN subscriptions_json TEXT"))


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

