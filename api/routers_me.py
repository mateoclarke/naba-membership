"""Self-service profile editing (Task 12) — requires member session JWT."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import BusinessMember, DirectoryProfile, Member
from .profile_uploads import append_profile_gallery, save_profile_logo, serialize_gallery
from .routers_admin import _profile_to_admin_detail
from .schemas import MyBusinessItem, ProfileAdminDetail, ProfileSelfUpdate
from .security import require_member

router = APIRouter(prefix="/api/v1/me", tags=["member-self"])


def _apply_self_update(profile: DirectoryProfile, body: ProfileSelfUpdate) -> None:
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)


@router.get("/profile", response_model=ProfileAdminDetail)
def get_my_profile(
    profile: DirectoryProfile = Depends(require_member),
    db: Session = Depends(get_db),
):
    member = db.get(Member, profile.member_id)
    return _profile_to_admin_detail(profile, member)


@router.put("/profile", response_model=ProfileAdminDetail)
def update_my_profile(
    body: ProfileSelfUpdate,
    profile: DirectoryProfile = Depends(require_member),
    db: Session = Depends(get_db),
):
    _apply_self_update(profile, body)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    member = db.get(Member, profile.member_id)
    return _profile_to_admin_detail(profile, member)


@router.post("/profile/logo", response_model=ProfileAdminDetail)
async def upload_my_logo(
    profile: DirectoryProfile = Depends(require_member),
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    public_path = await save_profile_logo(profile.id, file)
    profile.logo_url = public_path
    db.add(profile)
    db.commit()
    member = db.get(Member, profile.member_id)
    return _profile_to_admin_detail(profile, member)


@router.post("/profile/gallery")
async def upload_my_gallery(
    profile: DirectoryProfile = Depends(require_member),
    db: Session = Depends(get_db),
    files: List[UploadFile] = File(...),
):
    urls, new_urls = await append_profile_gallery(profile.id, files, profile.gallery_json)
    profile.gallery_json = serialize_gallery(urls)
    db.add(profile)
    db.commit()
    member = db.get(Member, profile.member_id)
    detail = _profile_to_admin_detail(profile, member)
    return {"profile": detail, "gallery": urls, "added": new_urls}


@router.get("/businesses", response_model=List[MyBusinessItem])
def list_my_businesses(
    profile: DirectoryProfile = Depends(require_member),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        select(BusinessMember, DirectoryProfile)
        .join(DirectoryProfile, DirectoryProfile.id == BusinessMember.business_profile_id)
        .where(
            BusinessMember.member_profile_id == profile.id,
            BusinessMember.can_edit.is_(True),
            DirectoryProfile.entry_type == "business",
        )
        .order_by(DirectoryProfile.display_name)
    ).all()
    return [
        MyBusinessItem(
            business_id=biz.id,
            display_name=biz.display_name,
            role_in_business=link.role_in_business,
            can_edit=link.can_edit,
        )
        for link, biz in rows
    ]


@router.put("/businesses/{business_id}/profile", response_model=ProfileAdminDetail)
def update_my_business_profile(
    business_id: int,
    body: ProfileSelfUpdate,
    profile: DirectoryProfile = Depends(require_member),
    db: Session = Depends(get_db),
):
    link = db.execute(
        select(BusinessMember).where(
            BusinessMember.business_profile_id == business_id,
            BusinessMember.member_profile_id == profile.id,
            BusinessMember.can_edit.is_(True),
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=403, detail="Not authorized for this business")

    business_profile = db.get(DirectoryProfile, business_id)
    if business_profile is None or business_profile.entry_type != "business":
        raise HTTPException(status_code=404, detail="Business profile not found")

    _apply_self_update(business_profile, body)
    db.add(business_profile)
    db.commit()
    db.refresh(business_profile)
    member = db.get(Member, business_profile.member_id)
    return _profile_to_admin_detail(business_profile, member)


@router.get("/businesses/{business_id}/profile", response_model=ProfileAdminDetail)
def get_my_business_profile(
    business_id: int,
    profile: DirectoryProfile = Depends(require_member),
    db: Session = Depends(get_db),
):
    link = db.execute(
        select(BusinessMember).where(
            BusinessMember.business_profile_id == business_id,
            BusinessMember.member_profile_id == profile.id,
            BusinessMember.can_edit.is_(True),
        )
    ).scalar_one_or_none()
    if link is None:
        raise HTTPException(status_code=403, detail="Not authorized for this business")
    business_profile = db.get(DirectoryProfile, business_id)
    if business_profile is None or business_profile.entry_type != "business":
        raise HTTPException(status_code=404, detail="Business profile not found")
    member = db.get(Member, business_profile.member_id)
    return _profile_to_admin_detail(business_profile, member)
