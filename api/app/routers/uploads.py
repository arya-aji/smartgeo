"""Uploads router."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from wss_common import queue, storage
from wss_common.config import settings
from wss_common.db import get_session
from wss_common.enums import JobStatus, JobType, ProcessingStatus
from wss_common.models import MapDocument, ProcessingJob, User
from wss_common.queue import build_message

from app.core.deps import get_current_user
from app.schemas import CompleteRequest, CompleteResponse, PresignRequest, PresignResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_ALLOWED_TYPES = [t.strip() for t in settings.upload_allowed_types.split(",") if t.strip()]


@router.post("/presign", response_model=PresignResponse)
def presign(
    req: PresignRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    if req.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid content type",
        )
    if req.size > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large",
        )

    object_key = storage.new_original_key(req.content_type, req.filename)
    doc = MapDocument(
        processing_status=ProcessingStatus.UPLOADING,
        original_object_key=object_key,
        uploaded_by=current_user.id,
        original_filename=req.filename,
        content_type=req.content_type,
        file_size=req.size,
        target_id=req.target_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    upload_url = storage.presign_put(object_key, content_type=req.content_type)
    return {
        "map_document_id": doc.id,
        "object_key": object_key,
        "upload_url": upload_url,
        "method": "PUT",
        "headers": {"Content-Type": req.content_type},
        "expires_in": settings.s3_presign_expire,
    }


@router.post("/complete", response_model=CompleteResponse)
def complete(
    req: CompleteRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    doc = db.query(MapDocument).filter(MapDocument.id == req.map_document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    try:
        exists = storage.object_exists(doc.original_object_key)
    except Exception as exc:
        logger.warning("Storage unreachable while checking object existence: %s", exc)
        exists = True

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Object not found in storage",
        )

    doc.source_width = req.width
    doc.source_height = req.height
    doc.file_size = req.file_size
    doc.processing_status = ProcessingStatus.UPLOADED

    job = ProcessingJob(
        map_document_id=doc.id,
        job_type=JobType.CV_PROCESS,
        status=JobStatus.PENDING,
        attempt=0,
    )
    db.add(job)
    db.flush()

    queue.enqueue(
        JobType.CV_PROCESS,
        build_message(
            job_id=str(job.id),
            map_document_id=str(doc.id),
            job_type=JobType.CV_PROCESS,
            attempt=0,
        ),
    )

    doc.processing_status = ProcessingStatus.QUEUED
    db.commit()
    db.refresh(doc)
    db.refresh(job)

    return {"map_document": doc, "job": job}
