from __future__ import annotations

from datetime import datetime, timezone

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db import get_db
from .models import BusinessMember, DirectoryProfile, Member
from .schemas import (
    BusinessMemberAdminItem,
    BusinessMemberAdminList,
    BusinessMemberCreate,
    BusinessMemberUpdate,
)
from .security import require_admin

router = APIRouter(prefix="/api/v1/admin/business-members", tags=["admin-business-members"])

_ORG_ENTRY_TYPES = frozenset({"business", "organization"})


def _to_admin_item(db: Session, row: BusinessMember) -> BusinessMemberAdminItem:
    business = db.get(DirectoryProfile, row.business_profile_id)
    member_profile = db.get(DirectoryProfile, row.member_profile_id)
    member = db.get(Member, member_profile.member_id) if member_profile else None
    return BusinessMemberAdminItem(
        id=row.id,
        business_profile_id=row.business_profile_id,
        member_profile_id=row.member_profile_id,
        role_in_business=row.role_in_business,
        can_edit=row.can_edit,
        created_at=row.created_at,
        business_display_name=business.display_name if business else None,
        member_display_name=member_profile.display_name if member_profile else None,
        member_email=member.email if member else None,
    )


@router.get("/", response_model=BusinessMemberAdminList)
def list_business_member_links(
    business_id: Optional[int] = Query(None),
    member_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    query = select(BusinessMember)
    if business_id is not None:
        query = query.where(BusinessMember.business_profile_id == business_id)
    if member_id is not None:
        query = query.where(BusinessMember.member_profile_id == member_id)

    rows = db.execute(query.order_by(BusinessMember.id)).scalars().all()
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    return BusinessMemberAdminList(
        items=[_to_admin_item(db, row) for row in rows],
        total=total,
    )


@router.post("/", response_model=BusinessMemberAdminItem)
def create_business_member_link(
    body: BusinessMemberCreate,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    business = db.get(DirectoryProfile, body.business_profile_id)
    member = db.get(DirectoryProfile, body.member_profile_id)
    if business is None or business.entry_type not in _ORG_ENTRY_TYPES:
        raise HTTPException(
            status_code=400,
            detail="business_profile_id must be a business or organization profile",
        )
    if member is None or member.entry_type != "individual":
        raise HTTPException(status_code=400, detail="member_profile_id must be an individual profile")

    existing = db.execute(
        select(BusinessMember).where(
            BusinessMember.business_profile_id == body.business_profile_id,
            BusinessMember.member_profile_id == body.member_profile_id,
        )
    ).scalar_one_or_none()
    if existing:
        existing.role_in_business = body.role_in_business
        existing.can_edit = body.can_edit
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return _to_admin_item(db, existing)

    row = BusinessMember(
        business_profile_id=body.business_profile_id,
        member_profile_id=body.member_profile_id,
        role_in_business=body.role_in_business,
        can_edit=body.can_edit,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_admin_item(db, row)


@router.patch("/{link_id}", response_model=BusinessMemberAdminItem)
def update_business_member_link(
    link_id: int,
    body: BusinessMemberUpdate,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    row = db.get(BusinessMember, link_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Link not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_admin_item(db, row)


@router.delete("/{link_id}")
def delete_business_member_link(
    link_id: int,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    row = db.get(BusinessMember, link_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Link not found")
    db.delete(row)
    db.commit()
    return {"status": "ok"}
