from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime, Enum, Boolean, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class MemberStatusEnum(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    NONE = "none"


class EntryTypeEnum(str, Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"
    BUSINESS = "business"


class Member(Base):
    """
    Internal member record seeded from MemberPress CSV.

    Contains PII and should never be exposed directly via public APIs.
    """

    __tablename__ = "members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Basic identity (from CSV)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    memberships_raw: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # JSON list of {title, status, expires_at, ...} from MemberPress sync
    subscriptions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    registered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    first_txn_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    latest_txn_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_province: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class DirectoryProfile(Base):
    """
    Public directory-safe profile derived from Member.

    Fields split into two groups:
    - WP-sourced: updated by the sync script on every run
    - Enrichment: managed locally (admin / self-service), preserved across syncs
    """

    __tablename__ = "directory_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    member_id: Mapped[int] = mapped_column(Integer, index=True)

    # --- WP-sourced (overwritten by sync) ---
    display_name: Mapped[str] = mapped_column(String, index=True)
    entry_type: Mapped[str] = mapped_column(String, index=True)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    organization: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    state_province: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    location_display: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tags_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    member_since_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    visibility_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # --- Enrichment (preserved across syncs) ---
    opted_in: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    opted_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    badges_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    gallery_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    social_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    show_city: Mapped[bool] = mapped_column(Boolean, default=True)
    show_member_since: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_connect: Mapped[bool] = mapped_column(Boolean, default=False)
    services_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    regions_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    categories_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    materials_csv: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Optional vanity slug for public URLs (unique when set). If null, effective slug is name-based + id.
    slug: Mapped[Optional[str]] = mapped_column(String, nullable=True, unique=True, index=True)


class ConnectMessage(Base):
    """Visitor outreach to a directory profile; moderated before delivery."""

    __tablename__ = "connect_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    recipient_profile_id: Mapped[int] = mapped_column(Integer, index=True)
    sender_name: Mapped[str] = mapped_column(String(200))
    sender_email: Mapped[str] = mapped_column(String(320))
    message_body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    honeypot_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class BusinessMember(Base):
    """Link members (individual profiles) to business profiles."""

    __tablename__ = "business_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_profile_id: Mapped[int] = mapped_column(Integer, index=True)
    member_profile_id: Mapped[int] = mapped_column(Integer, index=True)
    role_in_business: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

