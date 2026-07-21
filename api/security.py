"""Shared auth dependencies for admin and member routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from typing import Optional

from typing_extensions import Annotated

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import config
from .db import get_db
from .models import DirectoryProfile


def _decode_member_payload(raw: str) -> Optional[dict]:
    if not config.AUTH_JWT_SECRET:
        return None
    try:
        payload = jwt.decode(raw, config.AUTH_JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    if payload.get("typ") != "member":
        return None
    return payload


def _bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization[7:].strip() or None


def require_admin(
    x_admin_api_key: Annotated[Optional[str], Header()] = None,
    authorization: Annotated[Optional[str], Header()] = None,
) -> None:
    """
    Allow either:
      - ADMIN_API_KEY via X-Admin-API-Key or Bearer, or
      - member session JWT with admin=True (WordPress administrator at login).
    """
    if x_admin_api_key and config.ADMIN_API_KEY and x_admin_api_key == config.ADMIN_API_KEY:
        return

    bearer = _bearer_token(authorization)
    if bearer:
        if config.ADMIN_API_KEY and bearer == config.ADMIN_API_KEY:
            return
        payload = _decode_member_payload(bearer)
        if payload and payload.get("admin") is True:
            return

    if not config.ADMIN_API_KEY and not config.AUTH_JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Admin auth is not configured (ADMIN_API_KEY or AUTH_JWT_SECRET)",
        )
    raise HTTPException(status_code=401, detail="Unauthorized")


def issue_member_access_token(
    profile_id: int,
    *,
    is_admin: bool = False,
    membership_status: Optional[str] = None,
) -> tuple[str, int]:
    """Return (jwt, expires_in_seconds)."""
    if not config.AUTH_JWT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="AUTH_JWT_SECRET is not configured",
        )
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=config.AUTH_JWT_EXPIRE_SECONDS)
    payload = {
        "sub": str(profile_id),
        "typ": "member",
        "admin": bool(is_admin),
        "membership_status": (membership_status or "").strip().lower() or "none",
        "exp": exp,
        "iat": now,
    }
    token = jwt.encode(payload, config.AUTH_JWT_SECRET, algorithm="HS256")
    return token, config.AUTH_JWT_EXPIRE_SECONDS


def require_member(
    authorization: Annotated[Optional[str], Header()] = None,
    db: Session = Depends(get_db),
) -> DirectoryProfile:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    raw = authorization[7:].strip()
    if not config.AUTH_JWT_SECRET:
        raise HTTPException(status_code=503, detail="AUTH_JWT_SECRET is not configured")
    try:
        payload = jwt.decode(raw, config.AUTH_JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token") from None
    if payload.get("typ") != "member":
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        profile_id = int(payload.get("sub") or 0)
    except (TypeError, ValueError):
        profile_id = 0
    if not profile_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    profile = db.get(DirectoryProfile, profile_id)
    if profile is None:
        raise HTTPException(status_code=401, detail="Profile not found")
    return profile


def optional_admin_from_token(
    authorization: Annotated[Optional[str], Header()] = None,
) -> bool:
    """Return True if the bearer token is a member JWT with admin=True. Never raises."""
    bearer = _bearer_token(authorization)
    if not bearer:
        return False
    payload = _decode_member_payload(bearer)
    if not payload:
        return False
    return payload.get("admin") is True


def optional_membership_directory_access(
    authorization: Annotated[Optional[str], Header()] = None,
) -> bool:
    """
    True if the caller may browse the membership (non-business) directory:
    WP administrator JWT, or active membership status claim.
    """
    bearer = _bearer_token(authorization)
    if not bearer:
        return False
    payload = _decode_member_payload(bearer)
    if not payload:
        return False
    if payload.get("admin") is True:
        return True
    return (payload.get("membership_status") or "").strip().lower() == "active"