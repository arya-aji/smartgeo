"""Dashboard router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from wss_common import queue
from wss_common.db import get_session
from wss_common.enums import JobType, ProcessingStatus, TargetStatus
from wss_common.models import MapDocument, User, WssTarget

from app.core.deps import require_admin
from app.schemas import DashboardResponse

router = APIRouter()


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict:
    total_targets = db.query(func.count(WssTarget.id)).scalar() or 0
    completed_targets = (
        db.query(func.count(WssTarget.id)).filter(WssTarget.status == TargetStatus.COMPLETED).scalar() or 0
    )
    processing_targets = (
        db.query(func.count(WssTarget.id)).filter(WssTarget.status == TargetStatus.PROCESSING).scalar() or 0
    )
    queued_targets = (
        db.query(func.count(WssTarget.id)).filter(WssTarget.status == TargetStatus.PENDING).scalar() or 0
    )
    review_targets = (
        db.query(func.count(WssTarget.id)).filter(WssTarget.status == TargetStatus.NEEDS_REVIEW).scalar() or 0
    )
    failed_targets = (
        db.query(func.count(WssTarget.id)).filter(WssTarget.status == TargetStatus.FAILED).scalar() or 0
    )

    progress_percent = (completed_targets / total_targets * 100) if total_targets else 0.0

    cv_pending = queue.queue_length(JobType.CV_PROCESS)
    cv_processing = queue.processing_length(JobType.CV_PROCESS)
    geo_pending = queue.queue_length(JobType.GEO_PROCESS)

    operators = []
    for user in db.query(User).all():
        operators.append(
            {
                "id": user.id,
                "name": user.name,
                "username": user.username,
                "completed": (
                    db.query(func.count(WssTarget.id))
                    .filter(WssTarget.assigned_to == user.id, WssTarget.status == TargetStatus.COMPLETED)
                    .scalar()
                    or 0
                ),
                "assigned": (
                    db.query(func.count(WssTarget.id))
                    .filter(WssTarget.assigned_to == user.id, WssTarget.status == TargetStatus.ASSIGNED)
                    .scalar()
                    or 0
                ),
                "review": (
                    db.query(func.count(MapDocument.id))
                    .filter(
                        MapDocument.uploaded_by == user.id,
                        MapDocument.processing_status == ProcessingStatus.NEEDS_REVIEW,
                    )
                    .scalar()
                    or 0
                ),
                "failed": (
                    db.query(func.count(MapDocument.id))
                    .filter(
                        MapDocument.uploaded_by == user.id,
                        MapDocument.processing_status == ProcessingStatus.FAILED,
                    )
                    .scalar()
                    or 0
                ),
            }
        )

    return {
        "global": {
            "total": total_targets,
            "completed": completed_targets,
            "processing": processing_targets,
            "queued": queued_targets,
            "review": review_targets,
            "failed": failed_targets,
        },
        "progress_percent": round(progress_percent, 1),
        "queue": {
            "cv_pending": cv_pending,
            "cv_processing": cv_processing,
            "geo_pending": geo_pending,
        },
        "operators": operators,
    }
