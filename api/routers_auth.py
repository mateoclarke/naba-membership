"""Member login: WordPress JWT plugin validates credentials; API issues session JWT."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .auth_wp import authenticate_wp_user
from .db import get_db
from .models import DirectoryProfile, Member
from .schemas import LoginRequest, LoginResponse
from .security import issue_member_access_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: Session = Depends(get_db)):
    wp = await authenticate_wp_user(body.username, body.password)
    profile = db.get(DirectoryProfile, wp.user_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No directory profile for this account",
        )
    member = db.get(Member, profile.member_id)
    membership_status = (member.status if member else None) or "none"
    token, ttl = issue_member_access_token(
        profile.id,
        is_admin=wp.is_admin,
        membership_status=membership_status,
    )
    return LoginResponse(
        access_token=token,
        expires_in=ttl,
        is_admin=wp.is_admin,
        membership_status=membership_status,
    )
