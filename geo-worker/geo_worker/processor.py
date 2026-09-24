"""Orchestrate a single GEO_PROCESS job."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from wss_common.config import settings
from wss_common.db import session_scope
from wss_common.enums import DatasetStatus, JobStatus, ProcessingStatus
from wss_common.models import GeoJsonDataset, GeoJsonFeature, MapDocument, ProcessingJob
from wss_common.storage import download_file, maps_key, georeferenced_key, preview_key, upload_file

from geo_worker.geojson_match import find_feature_for_idsubsls
from geo_worker.transform import compute_transform, TransformResult
from geo_worker.rasterize import rasterize_cleaned_map, generate_preview
from geo_worker.validate import validate_geotiff

logger = logging.getLogger("geo_worker.processor")


class GeoProcessingError(Exception):
    """Recoverable or fatal error during geo processing."""

    def __init__(self, message: str, *, fatal: bool = False) -> None:
        super().__init__(message)
        self.fatal = fatal


def _get_latest_ready_dataset(session: Session) -> GeoJsonDataset | None:
    """Return the most recent READY GeoJsonDataset, or None."""
    stmt = (
        select(GeoJsonDataset)
        .where(GeoJsonDataset.status == DatasetStatus.READY)
        .order_by(GeoJsonDataset.created_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _load_dataset_for_job(
    session: Session, message: dict[str, Any]
) -> GeoJsonDataset:
    """Resolve the GeoJsonDataset for this job.

    If the job payload includes ``geojson_dataset_id``, use it directly.
    Otherwise fall back to the latest READY dataset. This documents the
    choice required by the stage-2 spec.
    """
    dataset_id = message.get("geojson_dataset_id")
    if dataset_id:
        dataset = session.get(GeoJsonDataset, uuid.UUID(str(dataset_id)))
        if dataset is not None:
            return dataset
        logger.warning(
            "Job payload dataset_id %s not found; falling back to latest READY", dataset_id
        )

    dataset = _get_latest_ready_dataset(session)
    if dataset is None:
        raise GeoProcessingError(
            "No READY GeoJSON dataset available for matching", fatal=True
        )
    return dataset


def _update_document_status(
    session: Session,
    document: MapDocument,
    status: ProcessingStatus,
    error_message: str | None = None,
) -> None:
    document.processing_status = status
    if error_message is not None:
        document.error_message = error_message
    session.commit()


def _update_job_status(
    session: Session,
    job: ProcessingJob,
    status: JobStatus,
    error_message: str | None = None,
) -> None:
    job.status = status
    if error_message is not None:
        job.error_message = error_message
    if status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
        job.completed_at = datetime.now(timezone.utc)
    session.commit()


def process_job(message: dict[str, Any]) -> None:
    """Execute the full GEO_PROCESS pipeline for a single job."""
    job_id = uuid.UUID(str(message["job_id"]))
    map_document_id = uuid.UUID(str(message["map_document_id"]))
    attempt = int(message.get("attempt", 1))

    tmp_dir = Path(tempfile.mkdtemp(prefix="wss_geo_"))
    try:
        with session_scope() as session:
            job = session.get(ProcessingJob, job_id)
            if job is None:
                raise GeoProcessingError(f"Job {job_id} not found", fatal=True)

            document = session.get(MapDocument, map_document_id)
            if document is None:
                raise GeoProcessingError(f"MapDocument {map_document_id} not found", fatal=True)

            job.attempt = attempt
            job.started_at = datetime.now(timezone.utc)
            job.status = JobStatus.RUNNING
            session.commit()

            idsubsls = document.idsubsls
            if not idsubsls:
                raise GeoProcessingError(
                    "MapDocument has no idsubsls; cannot match GeoJSON feature", fatal=True
                )

            # ------------------------------------------------------------------
            # 1. Load dataset & match feature
            # ------------------------------------------------------------------
            document.processing_status = ProcessingStatus.FINALIZING
            session.commit()

            dataset = _load_dataset_for_job(session, message)
            feature = find_feature_for_idsubsls(session, dataset.id, idsubsls)
            if feature is None:
                _update_document_status(
                    session,
                    document,
                    ProcessingStatus.FAILED,
                    error_message=f"No GeoJSON feature found for idsubsls={idsubsls} in dataset {dataset.id}",
                )
                _update_job_status(session, job, JobStatus.FAILED, error_message=document.error_message)
                return

            # ------------------------------------------------------------------
            # 2. Download cleaned map
            # ------------------------------------------------------------------
            cleaned_map_key = maps_key(idsubsls)
            local_map_path = tmp_dir / f"{idsubsls}.jpg"
            try:
                download_file(cleaned_map_key, local_map_path)
            except Exception as exc:
                raise GeoProcessingError(
                    f"Failed to download cleaned map {cleaned_map_key}: {exc}", fatal=False
                ) from exc

            # ------------------------------------------------------------------
            # 3. Compute transform
            # ------------------------------------------------------------------
            transform_result = compute_transform(feature.geometry, local_map_path)

            # Persist transform metadata on the document
            document.transform_matrix = {
                "a": transform_result.a,
                "b": transform_result.b,
                "c": transform_result.c,
                "d": transform_result.d,
                "e": transform_result.e,
                "f": transform_result.f,
                "source_bounds": transform_result.source_bounds,
                "geojson_dataset_id": str(dataset.id),
                "geojson_version": dataset.version,
            }
            session.commit()

            # ------------------------------------------------------------------
            # 4. Rasterize GeoTIFF
            # ------------------------------------------------------------------
            geotiff_path = tmp_dir / f"{idsubsls}.tif"
            try:
                rasterize_cleaned_map(
                    local_map_path,
                    geotiff_path,
                    transform=transform_result.to_affine(),
                    crs="EPSG:4326",
                )
            except Exception as exc:
                raise GeoProcessingError(
                    f"Rasterization failed: {exc}", fatal=False
                ) from exc

            # ------------------------------------------------------------------
            # 5. Validate
            # ------------------------------------------------------------------
            validation = validate_geotiff(
                geotiff_path,
                expected_bounds=transform_result.source_bounds,
                feature_geometry=feature.geometry,
            )
            if not validation.ok:
                raise GeoProcessingError(
                    f"GeoTIFF validation failed: {validation.reason}", fatal=False
                ) from validation.error

            # ------------------------------------------------------------------
            # 6. Upload outputs
            # ------------------------------------------------------------------
            geo_key = georeferenced_key(idsubsls)
            upload_file(geotiff_path, geo_key, content_type="image/tiff")

            preview_path = tmp_dir / f"{idsubsls}_preview.webp"
            try:
                generate_preview(local_map_path, preview_path)
                upload_file(preview_path, preview_key(idsubsls), content_type="image/webp")
                document.preview_object_key = preview_key(idsubsls)
            except Exception:
                logger.warning("Preview generation failed for %s; continuing without it", idsubsls)

            document.final_object_key = geo_key
            document.processing_status = ProcessingStatus.COMPLETED
            document.processed_at = datetime.now(timezone.utc)
            document.processing_attempts = attempt
            document.error_message = None
            session.commit()

            _update_job_status(session, job, JobStatus.SUCCEEDED)
            logger.info(
                "GEO_PROCESS completed for %s (dataset=%s, version=%s)",
                idsubsls,
                dataset.id,
                dataset.version,
            )

    except GeoProcessingError as exc:
        logger.error("GeoProcessingError: %s", exc)
        with session_scope() as session:
            document = session.get(MapDocument, map_document_id)
            job = session.get(ProcessingJob, job_id)
            if document is not None:
                document.processing_status = ProcessingStatus.FAILED
                document.error_message = str(exc)
                document.processing_attempts = attempt
                session.commit()
            if job is not None:
                _update_job_status(session, job, JobStatus.FAILED, error_message=str(exc))
        raise
    except Exception as exc:
        logger.exception("Unexpected error during GEO_PROCESS")
        with session_scope() as session:
            document = session.get(MapDocument, map_document_id)
            job = session.get(ProcessingJob, job_id)
            if document is not None:
                document.processing_status = ProcessingStatus.FAILED
                document.error_message = f"Unexpected error: {exc}"
                document.processing_attempts = attempt
                session.commit()
            if job is not None:
                _update_job_status(session, job, JobStatus.FAILED, error_message=str(exc))
        raise
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)
