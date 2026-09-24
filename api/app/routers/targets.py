"""Targets router."""

from __future__ import annotations

import math
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from wss_common import storage
from wss_common.config import settings
from wss_common.db import get_session
from wss_common.enums import TargetStatus
from wss_common.models import MapDocument, User, WssTarget

from app.core.deps import get_current_user, require_admin
from app.schemas import PaginatedTargets, TargetImportRequest, TargetImportResponse, WssTargetResponse

router = APIRouter()


@router.get("", response_model=PaginatedTargets)
def list_targets(
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    if page_size > 100:
        page_size = 100

    query = db.query(WssTarget)
    if status:
        query = query.filter(WssTarget.status == status)
    if q:
        query = query.filter(WssTarget.idsubsls.ilike(f"%{q}%"))

    total = query.count()
    pages = math.ceil(total / page_size) if page_size else 1
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    # Fetch the linked map documents in one query, then attach presigned URLs so
    # the Map view can preview/download the resulting map per region.
    doc_ids = [t.map_document_id for t in items if t.map_document_id]
    docs: dict = {}
    if doc_ids:
        for doc in db.query(MapDocument).filter(MapDocument.id.in_(doc_ids)).all():
            docs[doc.id] = doc

    enriched = []
    for target in items:
        item = WssTargetResponse.model_validate(target)
        doc = docs.get(target.map_document_id) if target.map_document_id else None
        if doc is not None:
            if doc.preview_object_key:
                try:
                    item.preview_url = storage.presign_get(doc.preview_object_key)
                except Exception:
                    item.preview_url = None
            if doc.final_object_key:
                try:
                    item.final_url = storage.presign_get(doc.final_object_key)
                except Exception:
                    item.final_url = None
                try:
                    item.download_url = storage.presign_get(
                        doc.final_object_key,
                        disposition=f'attachment; filename="{target.idsubsls}.jpg"',
                    )
                except Exception:
                    item.download_url = None
        enriched.append(item)

    return {
        "items": enriched,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.post("/import", response_model=TargetImportResponse)
def import_targets(
    req: TargetImportRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict:
    pattern = re.compile(settings.id_pattern)
    created = 0
    skipped = 0
    invalid = 0

    for ids in req.idsubsls:
        if not pattern.match(ids):
            invalid += 1
            continue
        existing = db.query(WssTarget).filter(WssTarget.idsubsls == ids).first()
        if existing:
            skipped += 1
            continue
        target = WssTarget(idsubsls=ids, status=TargetStatus.PENDING)
        db.add(target)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "invalid": invalid}


@router.delete("/{target_id}")
def delete_target(
    target_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> dict:
    target = db.query(WssTarget).filter(WssTarget.id == UUID(target_id)).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    db.delete(target)
    db.commit()
    return {"deleted": True}
