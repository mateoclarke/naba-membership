"""
Admin directory profile API: list, detail, partial update, logo/gallery uploads.
Requires ADMIN_API_KEY (Bearer or X-Admin-API-Key).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import DirectoryProfile, Member
from .profile_uploads import (
    append_profile_gallery,
    parse_gallery_urls,
    save_profile_logo,
    serialize_gallery,
    uploads_base,
)
from .routers_public_members import (
    _parse_csv,
    _parse_gallery_json,
    _parse_json_or_none,
)
from .schemas import (
    DirectoryProfilePublic,
    MembershipSubscriptionItem,
    PaginatedProfileAdmin,
    ProfileAdminDetail,
    ProfileAdminUpdate,
)
from .security import require_admin
from .slug import effective_slug

router = APIRouter(prefix="/api/v1/admin/profiles", tags=["admin-profiles"])


def _parse_subscriptions(member: Optional[Member]) -> List[MembershipSubscriptionItem]:
    raw = getattr(member, "subscriptions_json", None) if member else None
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    items: List[MembershipSubscriptionItem] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        try:
            items.append(MembershipSubscriptionItem.model_validate(row))
        except Exception:
            continue
    return items


def _profile_to_admin_detail(profile: DirectoryProfile, member: Optional[Member]) -> ProfileAdminDetail:
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
        "slug": effective_slug(profile),
    }
    merged = dto.model_copy(update=updates)
    return ProfileAdminDetail(
        **merged.model_dump(),
        member_id=profile.member_id,
        email=member.email if member else None,
        opted_in=profile.opted_in,
        opted_in_at=profile.opted_in_at.isoformat() if profile.opted_in_at else None,
        badges_csv=profile.badges_csv,
        show_city=profile.show_city,
        show_member_since=profile.show_member_since,
        social_json=profile.social_json,
        services_csv=profile.services_csv,
        regions_csv=profile.regions_csv,
        tags_csv=profile.tags_csv,
        categories_csv=profile.categories_csv,
        materials_csv=profile.materials_csv,
        gallery_json=profile.gallery_json,
        membership_status=member.status if member else None,
        subscriptions=_parse_subscriptions(member),
    )


@router.get("/", response_model=PaginatedProfileAdmin)
def list_admin_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    q: Optional[str] = Query(None),
    opted_in: Optional[bool] = Query(None),
    entry_type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    query = select(DirectoryProfile)
    if opted_in is not None:
        query = query.where(DirectoryProfile.opted_in.is_(opted_in))
    if entry_type:
        query = query.where(DirectoryProfile.entry_type == entry_type)
    if q:
        pattern = f"%{q.lower()}%"
        query = (
            query.outerjoin(Member, Member.id == DirectoryProfile.member_id)
            .where(
                func.lower(DirectoryProfile.display_name).like(pattern)
                | func.lower(DirectoryProfile.organization).like(pattern)
                | func.lower(DirectoryProfile.location_display).like(pattern)
                | func.lower(DirectoryProfile.tags_csv).like(pattern)
                | func.lower(Member.email).like(pattern)
                | func.lower(Member.first_name).like(pattern)
                | func.lower(Member.last_name).like(pattern)
            )
        )

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    offset = (page - 1) * page_size
    rows = db.execute(query.order_by(DirectoryProfile.id).offset(offset).limit(page_size)).scalars().all()

    items: List[ProfileAdminDetail] = []
    for profile in rows:
        member = db.get(Member, profile.member_id)
        items.append(_profile_to_admin_detail(profile, member))

    return PaginatedProfileAdmin(
        items=items,
        page=page,
        page_size=page_size,
        total=total or 0,
    )


@router.get("/{profile_id}", response_model=ProfileAdminDetail)
def get_admin_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    profile = db.get(DirectoryProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    member = db.get(Member, profile.member_id)
    return _profile_to_admin_detail(profile, member)


def _apply_profile_update(profile: DirectoryProfile, body: ProfileAdminUpdate) -> None:
    data = body.model_dump(exclude_unset=True)
    prev_opted = profile.opted_in
    for key, value in data.items():
        setattr(profile, key, value)
    if "opted_in" in data:
        if data["opted_in"] and not prev_opted:
            profile.opted_in_at = datetime.now(timezone.utc)
        elif not data["opted_in"]:
            profile.opted_in_at = None


@router.put("/{profile_id}", response_model=ProfileAdminDetail)
def update_admin_profile(
    profile_id: int,
    body: ProfileAdminUpdate,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    profile = db.get(DirectoryProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    _apply_profile_update(profile, body)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    member = db.get(Member, profile.member_id)
    return _profile_to_admin_detail(profile, member)


@router.post("/{profile_id}/logo")
async def upload_profile_logo(
    profile_id: int,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    _auth: None = Depends(require_admin),
):
    profile = db.get(DirectoryProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    public_path = await save_profile_logo(profile_id, file)
    profile.logo_url = public_path
    db.add(profile)
    db.commit()

    return {"logo_url": public_path}


@router.post("/{profile_id}/gallery")
async def upload_profile_gallery(
    profile_id: int,
    db: Session = Depends(get_db),
    files: List[UploadFile] = File(...),
    _auth: None = Depends(require_admin),
):
    profile = db.get(DirectoryProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    urls, new_urls = await append_profile_gallery(profile_id, files, profile.gallery_json)
    profile.gallery_json = serialize_gallery(urls)
    db.add(profile)
    db.commit()

    return {"gallery": urls, "added": new_urls}


def _safe_delete_gallery_file(profile_id: int, url: str) -> None:
    """Remove a gallery file if it lives under this profile's upload directory."""
    prefix = f"/uploads/profiles/{profile_id}/gallery/"
    if not url.startswith(prefix):
        return
    name = url[len(prefix) :].lstrip("/")
    if not name or ".." in name or Path(name).is_absolute():
        return
    path = uploads_base() / "profiles" / str(profile_id) / "gallery" / name
    try:
        path.resolve().relative_to((uploads_base() / "profiles" / str(profile_id) / "gallery").resolve())
    except ValueError:
        return
    if path.is_file():
        path.unlink()


@router.delete("/{profile_id}/gallery/{gallery_index}")
def delete_gallery_image(
    profile_id: int,
    gallery_index: int,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    profile = db.get(DirectoryProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    urls = parse_gallery_urls(profile.gallery_json)
    if gallery_index < 0 or gallery_index >= len(urls):
        raise HTTPException(status_code=404, detail="Gallery image not found")

    removed = urls.pop(gallery_index)
    profile.gallery_json = serialize_gallery(urls)
    db.add(profile)
    db.commit()
    _safe_delete_gallery_file(profile_id, removed)

    return {"gallery": urls, "removed": removed}

