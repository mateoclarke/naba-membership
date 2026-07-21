from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import config
from .connect_logic import (
    count_urls,
    matches_spam_heuristics,
    normalize_user_text,
    rate_limit_allow,
    rate_limit_undo,
)
from .db import get_db
from .models import ConnectMessage, DirectoryProfile
from .schemas import ConnectSubmit, ConnectSubmitResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/public", tags=["public-connect"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _referer_ok(request: Request) -> bool:
    if not config.CONNECT_REQUIRE_REFERER:
        return True
    ref = request.headers.get("referer") or request.headers.get("Referer") or ""
    ref = ref.strip()
    if not ref:
        return False
    if ref.startswith("http://testserver"):
        return True
    for origin in config.CORS_ORIGINS:
        o = origin.strip().rstrip("/")
        if o and ref.startswith(o):
            return True
    return False


@router.post("/connect", response_model=ConnectSubmitResponse, status_code=201)
def submit_connect(
    request: Request,
    body: ConnectSubmit,
    db: Session = Depends(get_db),
):
    if not _referer_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing Referer header")

    ip = _client_ip(request)
    if not rate_limit_allow(ip):
        raise HTTPException(
            status_code=429,
            detail="Too many submissions from this address. Try again later.",
        )

    try:
        profile = db.get(DirectoryProfile, body.recipient_id)
        if profile is None:
            raise HTTPException(status_code=404, detail="Recipient not found")
        if not profile.opted_in or not profile.allow_connect:
            raise HTTPException(
                status_code=400,
                detail="This member does not accept connect messages",
            )

        sender_name = normalize_user_text(body.sender_name, 100)
        message_body = normalize_user_text(body.message, 2000)
        if not sender_name:
            raise HTTPException(status_code=400, detail="Name is required")
        if len(message_body) < 10:
            raise HTTPException(
                status_code=400,
                detail="Message must be at least 10 characters",
            )

        honeypot = (body.website or "").strip()
        status = "pending"
        honeypot_value: Optional[str] = honeypot if honeypot else None

        if honeypot:
            status = "spam"
        elif matches_spam_heuristics(message_body):
            status = "spam"

        url_n = count_urls(message_body)
        if url_n > 2:
            logger.warning(
                "connect_message url_heavy recipient=%s urls=%s ip=%s",
                body.recipient_id,
                url_n,
                ip,
            )

        row = ConnectMessage(
            recipient_profile_id=body.recipient_id,
            sender_name=sender_name,
            sender_email=str(body.sender_email),
            message_body=message_body,
            status=status,
            created_at=datetime.utcnow(),
            reviewed_at=None,
            ip_address=ip,
            honeypot_value=honeypot_value,
        )
        db.add(row)
        db.commit()

        logger.info(
            "connect_message id=%s recipient=%s status=%s ip=%s",
            row.id,
            row.recipient_profile_id,
            row.status,
            ip,
        )

        return ConnectSubmitResponse(
            status="pending",
            message="Your message has been submitted for review.",
        )
    except HTTPException:
        rate_limit_undo(ip)
        raise
