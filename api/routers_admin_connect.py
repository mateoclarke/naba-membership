from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import ConnectMessage
from .schemas import ConnectMessageAdmin, ConnectReviewBody
from .security import require_admin

router = APIRouter(prefix="/api/v1/admin/connect", tags=["admin-connect"])


@router.get("/", response_model=List[ConnectMessageAdmin])
def list_connect_messages(
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    q = select(ConnectMessage).order_by(ConnectMessage.created_at.desc())
    if status:
        q = q.where(ConnectMessage.status == status)
    rows = db.execute(q).scalars().all()
    return list(rows)


@router.put("/{message_id}", response_model=ConnectMessageAdmin)
def review_connect_message(
    message_id: int,
    body: ConnectReviewBody,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_admin),
):
    row = db.get(ConnectMessage, message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Message not found")
    row.status = body.status
    row.reviewed_at = datetime.utcnow()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
