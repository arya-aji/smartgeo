"""Georeference router (stage 2 stub)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from wss_common import queue, storage
from wss_common.db import get_session
from wss_common.enums import JobStatus, JobType, ProcessingStatus
from wss_common.models import GeoJsonDataset, MapDocument, ProcessingJob, User
from wss_common.queue import build_message

from app.core.deps import get_current_user
from app.schemas import GeoreferenceDetailResponse, GeoreferenceRequest, GeoreferenceResponse, JobResponse

router = APIRouter()


@router.post("", response_model=GeoreferenceResponse)
def create_georeference(
    req: GeoreferenceRequest,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    doc = db.query(MapDocument).filter(MapDocument.id == req.map_document_id).first()
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Map document not found")
    dataset = db.query(GeoJsonDataset).filter(GeoJsonDataset.id == req.dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dataset not found")

    job = ProcessingJob(
        map_document_id=doc.id,
        job_type=JobType.GEO_PROCESS,
        status=JobStatus.PENDING,
        attempt=0,
    )
    db.add(job)
    db.flush()

    queue.enqueue(
        JobType.GEO_PROCESS,
        build_message(
            job_id=str(job.id),
            map_document_id=str(doc.id),
            job_type=JobType.GEO_PROCESS,
            attempt=0,
        ),
    )

    doc.processing_status = ProcessingStatus.QUEUED
    db.commit()
    db.refresh(job)
    return {"job": job}


@router.get("/{job_id}", response_model=GeoreferenceDetailResponse)
def get_georeference(
    job_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == UUID(job_id)).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    output_key = None
    if job.status == JobStatus.SUCCEEDED and job.map_document_id:
        doc = db.query(MapDocument).filter(MapDocument.id == job.map_document_id).first()
        if doc and doc.idsubsls:
            output_key = storage.georeferenced_key(doc.idsubsls)

    return {"job": job, "output_object_key": output_key}


@router.post("/{job_id}/accept")
def accept_georeference(
    job_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == UUID(job_id)).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return {"accepted": True}


@router.post("/{job_id}/retry", response_model=JobResponse)
def retry_georeference(
    job_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> ProcessingJob:
    job = db.query(ProcessingJob).filter(ProcessingJob.id == UUID(job_id)).first()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = JobStatus.PENDING
    job.attempt += 1

    doc = db.query(MapDocument).filter(MapDocument.id == job.map_document_id).first()
    if doc is not None:
        doc.processing_status = ProcessingStatus.QUEUED

    queue.enqueue(
        JobType.GEO_PROCESS,
        build_message(
            job_id=str(job.id),
            map_document_id=str(job.map_document_id),
            job_type=JobType.GEO_PROCESS,
            attempt=job.attempt,
        ),
    )

    db.commit()
    db.refresh(job)
    return job
