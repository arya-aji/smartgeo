"""Batches router."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from wss_common.db import get_session
from wss_common.enums import TargetStatus
from wss_common.models import User, WssTarget

from app.core.deps import get_current_user
from app.schemas import BatchClaimRequest, BatchClaimResponse

router = APIRouter()


@router.post("/claim", response_model=BatchClaimResponse)
def claim_batch(
    req: BatchClaimRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    targets = db.execute(
        select(WssTarget)
        .where(WssTarget.status == TargetStatus.PENDING)
        .order_by(WssTarget.created_at)
        .limit(req.size)
        .with_for_update(skip_locked=True)
    ).scalars().all()

    for t in targets:
        t.status = TargetStatus.ASSIGNED
        t.assigned_to = current_user.id
        t.assigned_at = datetime.now(timezone.utc)

    db.flush()

    remaining = (
        db.query(WssTarget)
        .filter(WssTarget.status == TargetStatus.PENDING)
        .count()
    )

    db.commit()
    return {"targets": targets, "remaining": remaining}
