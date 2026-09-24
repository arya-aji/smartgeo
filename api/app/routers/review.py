"""Review router."""

from __future__ import annotations

import math
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from wss_common.config import settings
from wss_common.db import get_session
from wss_common.enums import ProcessingStatus
from wss_common.models import MapDocument, User

from app.core.deps import get_current_user
from app.schemas import (
    MapDocumentDetail,
    MapDocumentSummary,
    PaginationEnvelope,
    ReviewAcceptRequest,
    ReviewManualIdRequest,
)
from app.services.finalize import promote_review_output
from app.services.urls import attach_detail_urls, attach_summary

router = APIRouter()


@router.get("", response_model=PaginationEnvelope)
def list_review(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    if page_size > 100:
        page_size = 100

    query = (
        db.query(MapDocument)
        .filter(MapDocument.processing_status == ProcessingStatus.NEEDS_REVIEW)
        .order_by(MapDocument.created_at.desc(), MapDocument.id.desc())
    )
    total = query.count()
    pages = math.ceil(total / page_size) if page_size else 1
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    enriched = []
    for doc in items:
        summary = MapDocumentSummary.model_validate(doc)
        # A document awaiting review stores its output under review_object_key
        # (preview_object_key is only populated for COMPLETED documents).
        attach_summary(db, doc, summary, doc.review_object_key or doc.preview_object_key)
        enriched.append(summary)

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.post("/{doc_id}/accept", response_model=MapDocumentDetail)
def accept_review(
    doc_id: str,
    req: ReviewAcceptRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MapDocumentDetail:
    doc = db.query(MapDocument).filter(MapDocument.id == UUID(doc_id)).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    idsubsls = req.idsubsls
    if not idsubsls:
        idsubsls = doc.idsubsls or doc.ocr_raw
    if not idsubsls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No idsubsls available",
        )

    promote_review_output(db, doc, idsubsls)
    db.commit()
    db.refresh(doc)

    return attach_detail_urls(db, doc, MapDocumentDetail.model_validate(doc))


@router.post("/{doc_id}/manual-id", response_model=MapDocumentDetail)
def manual_id_review(
    doc_id: str,
    req: ReviewManualIdRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MapDocumentDetail:
    doc = db.query(MapDocument).filter(MapDocument.id == UUID(doc_id)).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not re.match(settings.id_pattern, req.idsubsls):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid idsubsls format",
        )

    promote_review_output(db, doc, req.idsubsls)
    db.commit()
    db.refresh(doc)

    return attach_detail_urls(db, doc, MapDocumentDetail.model_validate(doc))
