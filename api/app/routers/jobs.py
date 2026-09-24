"""Jobs router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from wss_common import queue
from wss_common.db import get_session
from wss_common.enums import JobStatus, JobType, ProcessingStatus
from wss_common.models import MapDocument, ProcessingJob, User
from wss_common.queue import build_message

from app.core.deps import get_current_user
from app.schemas import JobCreateRequest, JobResponse

router = APIRouter()


@router.post("", response_model=JobResponse)
def create_job(
    req: JobCreateRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProcessingJob:
    doc = db.query(MapDocument).filter(MapDocument.id == req.map_document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

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
    db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProcessingJob:
    from uuid import UUID

    job = db.query(ProcessingJob).filter(ProcessingJob.id == UUID(job_id)).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_job(
    job_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProcessingJob:
    from uuid import UUID

    job = db.query(ProcessingJob).filter(ProcessingJob.id == UUID(job_id)).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = JobStatus.PENDING
    job.attempt += 1

    doc = db.query(MapDocument).filter(MapDocument.id == job.map_document_id).first()
    if doc is not None:
        doc.processing_status = ProcessingStatus.QUEUED

    queue.enqueue(
        JobType.CV_PROCESS,
        build_message(
            job_id=str(job.id),
            map_document_id=str(job.map_document_id),
            job_type=JobType.CV_PROCESS,
            attempt=job.attempt,
        ),
    )

    db.commit()
    db.refresh(job)
    return job
