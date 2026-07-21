from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator


ALLOWED_CATEGORY_VALUES = {
    "professional",
    "owner/builder",
    "vendor",
    "educator",
}

ALLOWED_MATERIAL_VALUES = {
    "adobe",
    "compressed earth block (ceb)",
    "rammed earth",
    "cob",
    "light straw clay",
    "hempcrete",
    "timber framing",
    "straw bale",
    "natural plaster",
}


def _normalize_csv(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    parts: list[str] = []
    seen: set[str] = set()
    for token in value.split(","):
        t = token.strip().lower()
        if not t or t in seen:
            continue
        seen.add(t)
        parts.append(t)
    return ",".join(parts) if parts else None


def _validate_allowed_csv(value: Optional[str], allowed: set[str], field_name: str) -> Optional[str]:
    normalized = _normalize_csv(value)
    if normalized is None:
        return None
    values = normalized.split(",")
    invalid = [v for v in values if v not in allowed]
    if invalid:
        raise ValueError(
            f"{field_name} contains unsupported values: {', '.join(invalid)}"
        )
    return normalized


class DirectoryProfileListItem(BaseModel):
    """Fields exposed in the paginated directory list (subset of full profile)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    entry_type: str
    role: Optional[str] = None
    organization: Optional[str] = None

    city: Optional[str] = None
    state_province: Optional[str] = None
    country: Optional[str] = None
    location_display: Optional[str] = None

    website_url: Optional[HttpUrl] = None
    tags: List[str] = []
    badges: List[str] = []
    categories: List[str] = []
    materials: List[str] = []

    member_since_year: Optional[int] = None
    logo_url: Optional[str] = None
    slug: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Admin-only fields (populated only when show_all=true)
    membership_status: Optional[str] = None
    last_active_date: Optional[str] = None
    opted_in: Optional[bool] = None


class DirectoryProfilePublic(BaseModel):
    """Full public profile for detail views and admin flows."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    entry_type: str
    role: Optional[str] = None
    organization: Optional[str] = None

    city: Optional[str] = None
    state_province: Optional[str] = None
    country: Optional[str] = None
    location_display: Optional[str] = None

    website_url: Optional[HttpUrl] = None
    tags: List[str] = []
    badges: List[str] = []
    categories: List[str] = []
    materials: List[str] = []

    member_since_year: Optional[int] = None

    bio: Optional[str] = None
    logo_url: Optional[str] = None
    gallery: List[str] = []
    phone: Optional[str] = None
    social: Optional[Dict[str, Any]] = None
    allow_connect: bool = False
    services: List[str] = []
    regions: List[str] = []
    slug: Optional[str] = None
    team: List[dict] = []
    affiliated_businesses: List[dict] = []


class PaginatedDirectoryProfiles(BaseModel):
    items: List[DirectoryProfileListItem]
    page: int
    page_size: int
    total: int


class DirectoryMapItem(BaseModel):
    """Lightweight payload for interactive map rendering."""

    id: int
    display_name: str
    entry_type: str
    role: Optional[str] = None
    organization: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    country: Optional[str] = None
    location_display: Optional[str] = None
    website_url: Optional[HttpUrl] = None
    tags: List[str] = []
    badges: List[str] = []
    slug: Optional[str] = None
    latitude: float
    longitude: float


class DirectoryMapResponse(BaseModel):
    items: List[DirectoryMapItem]


class ConnectSubmit(BaseModel):
    recipient_id: int
    sender_name: str = Field(..., max_length=100)
    sender_email: EmailStr
    message: str = Field(..., max_length=2000)
    website: str = ""  # honeypot — must be empty for humans


class ConnectSubmitResponse(BaseModel):
    status: str
    message: str


class ConnectMessageAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    recipient_profile_id: int
    sender_name: str
    sender_email: str
    message_body: str
    status: str
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    honeypot_value: Optional[str] = None


class ConnectReviewBody(BaseModel):
    status: Literal["approved", "rejected", "spam"]


def _validate_logo_url(value: Optional[str]) -> Optional[str]:
    """Allow https image URLs, local /uploads paths, or clear with empty string."""
    if value is None:
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    lower = trimmed.lower()
    if lower.startswith("https://") or lower.startswith("http://"):
        return trimmed
    if trimmed.startswith("/uploads/"):
        return trimmed
    raise ValueError("logo_url must be an http(s) URL or an /uploads/... path")


class ProfileAdminUpdate(BaseModel):
    opted_in: Optional[bool] = None
    badges_csv: Optional[str] = None
    bio: Optional[str] = None
    entry_type: Optional[str] = None
    organization: Optional[str] = None
    show_city: Optional[bool] = None
    show_member_since: Optional[bool] = None
    allow_connect: Optional[bool] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    social_json: Optional[str] = None
    services_csv: Optional[str] = None
    regions_csv: Optional[str] = None
    tags_csv: Optional[str] = None
    categories_csv: Optional[str] = None
    materials_csv: Optional[str] = None
    logo_url: Optional[str] = None

    @field_validator("categories_csv")
    @classmethod
    def validate_categories_csv(cls, value: Optional[str]) -> Optional[str]:
        return _validate_allowed_csv(value, ALLOWED_CATEGORY_VALUES, "categories_csv")

    @field_validator("materials_csv")
    @classmethod
    def validate_materials_csv(cls, value: Optional[str]) -> Optional[str]:
        return _validate_allowed_csv(value, ALLOWED_MATERIAL_VALUES, "materials_csv")

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_logo_url(value)

class MembershipSubscriptionItem(BaseModel):
    """One MemberPress subscription / membership entitlement for /me or admin."""

    membership_id: Optional[int] = None
    subscription_id: Optional[int] = None
    title: str
    status: str
    period: Optional[str] = None
    period_type: Optional[str] = None
    created_at: Optional[str] = None
    expires_at: Optional[str] = None
    is_lifetime: bool = False


class ProfileAdminDetail(DirectoryProfilePublic):
    """Admin view: full enrichment, no privacy stripping, member email."""

    member_id: int
    email: Optional[str] = None
    opted_in: bool
    opted_in_at: Optional[str] = None
    badges_csv: Optional[str] = None
    show_city: bool
    show_member_since: bool
    social_json: Optional[str] = None
    services_csv: Optional[str] = None
    regions_csv: Optional[str] = None
    tags_csv: Optional[str] = None
    categories_csv: Optional[str] = None
    materials_csv: Optional[str] = None
    gallery_json: Optional[str] = None
    membership_status: Optional[str] = None
    subscriptions: List[MembershipSubscriptionItem] = Field(default_factory=list)


class PaginatedProfileAdmin(BaseModel):
    items: List[ProfileAdminDetail]
    page: int
    page_size: int
    total: int


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    is_admin: bool = False
    membership_status: Optional[str] = None


class ProfileSelfUpdate(BaseModel):
    """Fields members may edit (Task 12); excludes admin-only columns."""

    bio: Optional[str] = None
    website_url: Optional[str] = None
    phone: Optional[str] = None
    social_json: Optional[str] = None
    show_city: Optional[bool] = None
    show_member_since: Optional[bool] = None
    allow_connect: Optional[bool] = None
    services_csv: Optional[str] = None
    regions_csv: Optional[str] = None
    tags_csv: Optional[str] = None
    categories_csv: Optional[str] = None
    materials_csv: Optional[str] = None
    organization: Optional[str] = None
    logo_url: Optional[str] = None

    @field_validator("categories_csv")
    @classmethod
    def validate_categories_csv(cls, value: Optional[str]) -> Optional[str]:
        return _validate_allowed_csv(value, ALLOWED_CATEGORY_VALUES, "categories_csv")

    @field_validator("materials_csv")
    @classmethod
    def validate_materials_csv(cls, value: Optional[str]) -> Optional[str]:
        return _validate_allowed_csv(value, ALLOWED_MATERIAL_VALUES, "materials_csv")

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: Optional[str]) -> Optional[str]:
        return _validate_logo_url(value)

class BusinessMemberCreate(BaseModel):
    business_profile_id: int
    member_profile_id: int
    role_in_business: Optional[str] = None
    can_edit: bool = False


class BusinessMemberUpdate(BaseModel):
    role_in_business: Optional[str] = None
    can_edit: Optional[bool] = None


class BusinessMemberAdminItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_profile_id: int
    member_profile_id: int
    role_in_business: Optional[str] = None
    can_edit: bool
    created_at: datetime
    business_display_name: Optional[str] = None
    member_display_name: Optional[str] = None
    member_email: Optional[str] = None


class BusinessMemberAdminList(BaseModel):
    items: List[BusinessMemberAdminItem]
    total: int


class MyBusinessItem(BaseModel):
    business_id: int
    display_name: str
    role_in_business: Optional[str] = None
    can_edit: bool
