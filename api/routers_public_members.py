from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import BusinessMember, DirectoryProfile, Member
from .security import optional_admin_from_token, optional_membership_directory_access
from .slug import effective_slug, parse_trailing_profile_id
from .schemas import (
    DirectoryMapItem,
    DirectoryMapResponse,
    DirectoryProfileListItem,
    DirectoryProfilePublic,
    PaginatedDirectoryProfiles,
)


router = APIRouter(prefix="/api/v1/public/members", tags=["public-members"])


def _parse_csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [t.strip() for t in value.split(",") if t.strip()]


def _parse_json_or_none(value: Optional[str]) -> Optional[dict]:
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _parse_gallery_json(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        data = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(data, list):
        return [str(x) for x in data if x is not None and str(x).strip()]
    return []


def _profile_to_list_item(
    profile: DirectoryProfile,
    member: Optional[Member] = None,
    include_admin: bool = False,
) -> DirectoryProfileListItem:
    """Build list-view DTO (no bio/gallery/phone/social/services/regions)."""
    dto = DirectoryProfilePublic.model_validate(profile, from_attributes=True)
    updates: dict = {
        "tags": _parse_csv(profile.tags_csv),
        "badges": _parse_csv(profile.badges_csv),
        "categories": _parse_csv(profile.categories_csv),
        "materials": _parse_csv(profile.materials_csv),
    }
    if not profile.show_city:
        updates["city"] = None
        updates["state_province"] = None
        updates["location_display"] = None
    if not profile.show_member_since:
        updates["member_since_year"] = None
    merged = dto.model_copy(update=updates)
    item = DirectoryProfileListItem(
        id=merged.id,
        display_name=merged.display_name,
        entry_type=merged.entry_type,
        role=merged.role,
        organization=merged.organization,
        city=merged.city,
        state_province=merged.state_province,
        country=merged.country,
        location_display=merged.location_display,
        website_url=merged.website_url,
        tags=merged.tags,
        badges=merged.badges,
        categories=merged.categories,
        materials=merged.materials,
        member_since_year=merged.member_since_year,
        logo_url=merged.logo_url,
        slug=effective_slug(profile),
        latitude=profile.latitude,
        longitude=profile.longitude,
    )
    if include_admin:
        item.opted_in = profile.opted_in
        if member:
            item.membership_status = member.status
            if member.latest_txn_at:
                item.last_active_date = member.latest_txn_at.strftime("%Y-%m-%d")
    return item


def _profile_to_detail(profile: DirectoryProfile, db: Optional[Session] = None) -> DirectoryProfilePublic:
    """Full public DTO for detail views, respecting privacy prefs."""
    dto = DirectoryProfilePublic.model_validate(profile, from_attributes=True)
    updates: dict = {
        "tags": _parse_csv(profile.tags_csv),
        "badges": _parse_csv(profile.badges_csv),
        "categories": _parse_csv(profile.categories_csv),
        "materials": _parse_csv(profile.materials_csv),
        "gallery": _parse_gallery_json(profile.gallery_json),
        "social": _parse_json_or_none(profile.social_json),
        "services": _parse_csv(profile.services_csv),
        "regions": _parse_csv(profile.regions_csv),
    }
    if not profile.show_city:
        updates["city"] = None
        updates["state_province"] = None
        updates["location_display"] = None
    if not profile.show_member_since:
        updates["member_since_year"] = None
    if db is not None and profile.entry_type == "business":
        team_links = db.execute(
            select(BusinessMember, DirectoryProfile)
            .join(
                DirectoryProfile,
                DirectoryProfile.id == BusinessMember.member_profile_id,
            )
            .where(BusinessMember.business_profile_id == profile.id)
            .order_by(BusinessMember.id)
        ).all()
        updates["team"] = [
            {
                "id": member_profile.id,
                "display_name": member_profile.display_name,
                "role_in_business": link.role_in_business,
                "slug": effective_slug(member_profile),
            }
            for link, member_profile in team_links
            if member_profile.opted_in
        ]
    elif db is not None:
        biz_links = db.execute(
            select(BusinessMember, DirectoryProfile)
            .join(
                DirectoryProfile,
                DirectoryProfile.id == BusinessMember.business_profile_id,
            )
            .where(BusinessMember.member_profile_id == profile.id)
            .order_by(BusinessMember.id)
        ).all()
        updates["affiliated_businesses"] = [
            {
                "id": business_profile.id,
                "display_name": business_profile.display_name,
                "role_in_business": link.role_in_business,
                "slug": effective_slug(business_profile),
            }
            for link, business_profile in biz_links
            if business_profile.opted_in
        ]

    merged = dto.model_copy(update=updates)
    return merged.model_copy(update={"slug": effective_slug(profile)})


def _visibility_filter():
    """Opted-in is the sole gate for directory visibility.

    visibility_public (derived from WP membership status) is retained
    as metadata but does not control whether a profile appears.
    """
    return (DirectoryProfile.opted_in.is_(True),)


def _profile_matches_filters(
    profile: DirectoryProfile,
    q: Optional[str],
    entry_type: Optional[str],
    country: Optional[str],
    state: Optional[str],
) -> bool:
    if entry_type and profile.entry_type != entry_type:
        return False
    if country and profile.country != country:
        return False
    if state and profile.state_province != state:
        return False
    if q:
        ql = q.lower()
        fields = [
            profile.display_name,
            profile.organization,
            profile.location_display,
            profile.tags_csv,
        ]
        if not any(ql in (f or "").lower() for f in fields):
            return False
    return True


async def _list_public_members_wordpress(
    page: int,
    page_size: int,
    q: Optional[str],
    entry_type: Optional[str],
    country: Optional[str],
    state: Optional[str],
) -> PaginatedDirectoryProfiles:
    if not config.WP_API_URL or not config.WP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="DATA_SOURCE=wordpress requires WP_API_URL and WP_API_KEY",
        )

    from scripts.sync_from_wordpress import map_member, map_profile

    from .wp_client import fetch_all_members_async

    raw = await fetch_all_members_async(config.WP_API_URL, config.WP_API_KEY)

    visible: list[DirectoryProfile] = []
    for data in raw:
        wp_id = data.get("id")
        if not wp_id:
            continue
        member = map_member(data)
        profile = map_profile(data, member)
        if not profile.visibility_public:
            continue
        if not _profile_matches_filters(profile, q, entry_type, country, state):
            continue
        visible.append(profile)

    total = len(visible)
    offset = (page - 1) * page_size
    page_rows = visible[offset : offset + page_size]

    items = [_profile_to_list_item(p) for p in page_rows]

    return PaginatedDirectoryProfiles(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/", response_model=PaginatedDirectoryProfiles)
async def list_public_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    q: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    state: Optional[str] = Query(None, alias="state_province"),
    show_all: bool = Query(False),
    is_admin: bool = Depends(optional_admin_from_token),
    can_view_members: bool = Depends(optional_membership_directory_access),
    db: Session = Depends(get_db),
):
    # Membership directory (individuals/orgs) requires active member or admin.
    # Business directory remains publicly browsable.
    membership_types = {"individual", "organization"}
    if entry_type in membership_types and not can_view_members:
        raise HTTPException(
            status_code=401,
            detail="Sign in with an active membership to view the membership directory",
        )

    if config.DATA_SOURCE == "wordpress":
        if not can_view_members:
            # Anonymous / inactive: businesses only
            entry_type = "business"
        return await _list_public_members_wordpress(
            page=page,
            page_size=page_size,
            q=q,
            entry_type=entry_type,
            country=country,
            state=state,
        )

    skip_optin = show_all and is_admin
    query = select(DirectoryProfile)
    if not skip_optin:
        query = query.where(*_visibility_filter())

    if not can_view_members:
        query = query.where(DirectoryProfile.entry_type == "business")
    elif entry_type:
        query = query.where(DirectoryProfile.entry_type == entry_type)
    if country:
        query = query.where(DirectoryProfile.country == country)
    if state:
        query = query.where(DirectoryProfile.state_province == state)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            func.lower(DirectoryProfile.display_name).like(pattern)
            | func.lower(DirectoryProfile.organization).like(pattern)
            | func.lower(DirectoryProfile.location_display).like(pattern)
            | func.lower(DirectoryProfile.tags_csv).like(pattern)
        )

    total = db.scalar(select(func.count()).select_from(query.subquery()))

    offset = (page - 1) * page_size
    results = db.execute(query.offset(offset).limit(page_size)).scalars().all()

    if skip_optin:
        member_map: dict[int, Member] = {}
        member_ids = [p.member_id for p in results]
        if member_ids:
            members = db.execute(
                select(Member).where(Member.id.in_(member_ids))
            ).scalars().all()
            member_map = {m.id: m for m in members}
        items = [
            _profile_to_list_item(p, member=member_map.get(p.member_id), include_admin=True)
            for p in results
        ]
    else:
        items = [_profile_to_list_item(p) for p in results]

    return PaginatedDirectoryProfiles(
        items=items,
        page=page,
        page_size=page_size,
        total=total or 0,
    )


@router.get("/map", response_model=DirectoryMapResponse)
async def list_public_member_map_points(
    can_view_members: bool = Depends(optional_membership_directory_access),
    db: Session = Depends(get_db),
):
    """Opted-in profiles with coordinates — active members / admins only."""
    if not can_view_members:
        raise HTTPException(
            status_code=401,
            detail="Sign in with an active membership to view the member map",
        )
    rows = (
        db.execute(
            select(DirectoryProfile).where(
                *_visibility_filter(),
                DirectoryProfile.latitude.is_not(None),
                DirectoryProfile.longitude.is_not(None),
            )
        )
        .scalars()
        .all()
    )
    items = [
        DirectoryMapItem(
            id=p.id,
            display_name=p.display_name,
            entry_type=p.entry_type,
            role=p.role,
            organization=p.organization,
            city=p.city if p.show_city else None,
            state_province=p.state_province if p.show_city else None,
            country=p.country if p.show_city else None,
            location_display=p.location_display if p.show_city else None,
            website_url=p.website_url,
            tags=_parse_csv(p.tags_csv),
            badges=_parse_csv(p.badges_csv),
            slug=effective_slug(p),
            latitude=float(p.latitude),
            longitude=float(p.longitude),
        )
        for p in rows
    ]
    return DirectoryMapResponse(items=items)


async def _get_public_member_wordpress(member_id: int) -> DirectoryProfilePublic:
    if not config.WP_API_URL or not config.WP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="DATA_SOURCE=wordpress requires WP_API_URL and WP_API_KEY",
        )

    from scripts.sync_from_wordpress import map_member, map_profile

    from .wp_client import fetch_all_members_async

    raw = await fetch_all_members_async(config.WP_API_URL, config.WP_API_KEY)

    for data in raw:
        wp_id = data.get("id")
        if not wp_id or int(wp_id) != member_id:
            continue
        member = map_member(data)
        profile = map_profile(data, member)
        if not profile.visibility_public:
            raise HTTPException(status_code=404, detail="Not found")
        return _profile_to_detail(profile)

    raise HTTPException(status_code=404, detail="Not found")


def _get_profile_by_slug_sqlite(db: Session, slug: str) -> Optional[DirectoryProfile]:
    s = slug.strip()
    if not s:
        return None
    row = db.scalar(select(DirectoryProfile).where(DirectoryProfile.slug == s))
    if row is not None:
        return row
    pid = parse_trailing_profile_id(s)
    if pid is None:
        return None
    cand = db.get(DirectoryProfile, pid)
    if cand is None:
        return None
    if effective_slug(cand) != s:
        return None
    return cand


async def _get_public_member_by_slug_wordpress(slug: str) -> DirectoryProfilePublic:
    if not config.WP_API_URL or not config.WP_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="DATA_SOURCE=wordpress requires WP_API_URL and WP_API_KEY",
        )

    from scripts.sync_from_wordpress import map_member, map_profile

    from .wp_client import fetch_all_members_async

    want = slug.strip()
    raw = await fetch_all_members_async(config.WP_API_URL, config.WP_API_KEY)

    for data in raw:
        wp_id = data.get("id")
        if not wp_id:
            continue
        member = map_member(data)
        profile = map_profile(data, member)
        if not profile.visibility_public:
            continue
        if effective_slug(profile) == want:
            return _profile_to_detail(profile)

    raise HTTPException(status_code=404, detail="Not found")


@router.get("/by-slug/{slug}", response_model=DirectoryProfilePublic)
async def get_public_member_by_slug(
    slug: str,
    can_view_members: bool = Depends(optional_membership_directory_access),
    db: Session = Depends(get_db),
):
    """Resolve profile by vanity slug or computed `{slugify(name)}-{id}` segment."""
    if config.DATA_SOURCE == "wordpress":
        detail = await _get_public_member_by_slug_wordpress(slug)
        if detail.entry_type != "business" and not can_view_members:
            raise HTTPException(
                status_code=401,
                detail="Sign in with an active membership to view this profile",
            )
        return detail

    profile = _get_profile_by_slug_sqlite(db, slug)
    if profile is None or not profile.opted_in:
        raise HTTPException(status_code=404, detail="Not found")
    if profile.entry_type != "business" and not can_view_members:
        raise HTTPException(
            status_code=401,
            detail="Sign in with an active membership to view this profile",
        )
    return _profile_to_detail(profile, db=db)


@router.get("/{member_id}", response_model=DirectoryProfilePublic)
async def get_public_member(
    member_id: int,
    can_view_members: bool = Depends(optional_membership_directory_access),
    db: Session = Depends(get_db),
):
    """Full profile for a single opted-in directory member (detail page)."""
    if config.DATA_SOURCE == "wordpress":
        detail = await _get_public_member_wordpress(member_id)
        if detail.entry_type != "business" and not can_view_members:
            raise HTTPException(
                status_code=401,
                detail="Sign in with an active membership to view this profile",
            )
        return detail

    profile = db.get(DirectoryProfile, member_id)
    if profile is None or not profile.opted_in:
        raise HTTPException(status_code=404, detail="Not found")
    if profile.entry_type != "business" and not can_view_members:
        raise HTTPException(
            status_code=401,
            detail="Sign in with an active membership to view this profile",
        )
    return _profile_to_detail(profile, db=db)
