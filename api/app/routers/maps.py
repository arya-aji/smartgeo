"""Maps router."""

from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from wss_common import storage
from wss_common.db import get_session
from wss_common.enums import UserRole
from wss_common.models import MapDocument, User

from app.core.deps import get_current_user
from app.schemas import MapDocumentDetail, MapDocumentSummary, PaginationEnvelope

router = APIRouter()


@router.get("", response_model=PaginationEnvelope)
def list_maps(
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    mine: bool = False,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    if page_size > 100:
        page_size = 100

    query = db.query(MapDocument)

    if current_user.role != UserRole.ADMIN:
        query = query.filter(MapDocument.uploaded_by == current_user.id)
    elif mine:
        query = query.filter(MapDocument.uploaded_by == current_user.id)

    if status:
        query = query.filter(MapDocument.processing_status == status)
    if q:
        query = query.filter(MapDocument.idsubsls.ilike(f"%{q}%"))

    total = query.count()
    pages = math.ceil(total / page_size) if page_size else 1
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    enriched = []
    for doc in items:
        summary = MapDocumentSummary.model_validate(doc)
        summary.uploaded_by_name = (
            db.query(User.name).filter(User.id == doc.uploaded_by).scalar() if doc.uploaded_by else None
        )
        if doc.preview_object_key:
            try:
                summary.preview_url = storage.presign_get(doc.preview_object_key)
            except Exception:
                summary.preview_url = None
        enriched.append(summary)

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.get("/{map_id}", response_model=MapDocumentDetail)
def get_map(
    map_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> MapDocumentDetail:
    doc = db.query(MapDocument).filter(MapDocument.id == UUID(map_id)).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map not found")

    detail = MapDocumentDetail.model_validate(doc)
    detail.uploaded_by_name = (
        db.query(User.name).filter(User.id == doc.uploaded_by).scalar() if doc.uploaded_by else None
    )

    if doc.original_object_key:
        try:
            detail.original_url = storage.presign_get(doc.original_object_key)
        except Exception:
            detail.original_url = None
    if doc.final_object_key:
        try:
            detail.final_url = storage.presign_get(doc.final_object_key)
        except Exception:
            detail.final_url = None
    if doc.review_object_key:
        try:
            detail.review_url = storage.presign_get(doc.review_object_key)
        except Exception:
            detail.review_url = None
    if doc.preview_object_key:
        try:
            detail.preview_url = storage.presign_get(doc.preview_object_key)
        except Exception:
            detail.preview_url = None

    return detail
