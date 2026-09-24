"""Main processing orchestrator for a single map document job."""

from __future__ import annotations

import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from sqlalchemy import select

from wss_common import settings
from wss_common.db import session_scope
from wss_common.enums import ProcessingStatus, TargetStatus
from wss_common.models import MapDocument, ProcessingJob, WssTarget

from cv_worker.master import load_master_ids
from cv_worker.pipeline.enhance import enhance_image
from cv_worker.pipeline.id_search import search_id_candidates
from cv_worker.pipeline.ocr import get_ocr_backend
from cv_worker.pipeline.orientation import detect_orientation
from cv_worker.pipeline.paper import detect_paper
from cv_worker.pipeline.perspective import correct_perspective
from cv_worker.pipeline.quality import compute_quality
from cv_worker.pipeline.text import detect_text_regions
from cv_worker.pipeline.upscale import upscale_if_needed
from cv_worker.pipeline.validate import validate_id
from cv_worker.storage_io import fetch_original, upload_map, upload_preview, upload_review

logger = logging.getLogger(__name__)


class ProcessingError(Exception):
    """Raised when a pipeline stage fails unrecoverably."""

    def __init__(self, message: str, stage: str | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


def _update_status(
    session: Any,
    document: MapDocument,
    status: ProcessingStatus,
    job: ProcessingJob | None = None,
) -> None:
    """Update document status and optionally job status, then commit."""
    document.processing_status = status
    if job is not None:
        job.status = "RUNNING"
    session.commit()
    logger.info("Status -> %s (document %s)", status.value, document.id)


def _safe_upload_review(image: np.ndarray, document_id: str) -> str | None:
    try:
        return upload_review(image, str(document_id))
    except Exception as exc:
        logger.warning("Review upload failed: %s", exc)
        return None


def _safe_upload_map(image: np.ndarray, idsubsls: str) -> str | None:
    try:
        return upload_map(image, idsubsls)
    except Exception as exc:
        logger.warning("Map upload failed: %s", exc)
        return None


def _safe_upload_preview(image: np.ndarray, idsubsls: str) -> str | None:
    try:
        return upload_preview(image, idsubsls)
    except Exception as exc:
        logger.warning("Preview upload failed: %s", exc)
        return None


def process_document(map_document_id: str, job_id: str | None = None) -> dict[str, Any]:
    """Run the full CV pipeline for a single map document.

    Returns a dict with:
        - decision: "COMPLETED", "NEEDS_REVIEW", or "FAILED"
        - document_id: the processed document UUID
        - details: extra info for logging/metrics
    """
    document_id = uuid.UUID(map_document_id)
    master_ids = load_master_ids()
    ocr_backend = get_ocr_backend()
    timings: dict[str, float] = {}

    tmp_base = Path(settings.worker_tmp_dir) / str(document_id)
    tmp_base.mkdir(parents=True, exist_ok=True)

    try:
        with session_scope() as session:
            document = session.execute(
                select(MapDocument).where(MapDocument.id == document_id)
            ).scalar_one_or_none()
            if document is None:
                raise ProcessingError(f"Document {document_id} not found")

            job = None
            if job_id:
                job = session.execute(
                    select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id))
                ).scalar_one_or_none()

            # ------------------------------------------------------------------ #
            # 1. DETECTING_PAPER
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.DETECTING_PAPER, job)
            image = fetch_original(document.original_object_key, tmp_base)
            document.source_width = image.shape[1]
            document.source_height = image.shape[0]
            session.commit()

            paper_result = detect_paper(image)
            timings["paper"] = time.perf_counter() - t0
            document.paper_confidence = paper_result["confidence"]
            corners = paper_result["corners"]
            document.corners = [[int(p[0]), int(p[1])] for p in corners] if corners else None
            logger.info("Paper detection: method=%s confidence=%.2f", paper_result["method"], paper_result["confidence"])

            # ------------------------------------------------------------------ #
            # 2. CORRECTING_PERSPECTIVE
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.CORRECTING_PERSPECTIVE, job)
            if corners is None:
                raise ProcessingError("No paper corners detected", stage="perspective")
            perspective_result = correct_perspective(image, corners)
            warped = perspective_result["image"]
            document.transform_matrix = [[float(v) for v in row] for row in perspective_result["matrix"]]
            session.commit()
            timings["perspective"] = time.perf_counter() - t0

            # ------------------------------------------------------------------ #
            # 3. DETECTING_ORIENTATION
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.DETECTING_ORIENTATION, job)
            orientation_result = detect_orientation(warped, ocr_backend=ocr_backend, master_ids=master_ids)
            oriented = orientation_result["image"]
            document.orientation = orientation_result["degrees"]
            session.commit()
            timings["orientation"] = time.perf_counter() - t0
            logger.info("Orientation: %d degrees (score=%.2f)", orientation_result["degrees"], orientation_result["score"])

            # ------------------------------------------------------------------ #
            # 4. ENHANCING
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.ENHANCING, job)
            enhance_result = enhance_image(oriented)
            enhanced = enhance_result["enhanced"]
            binary = enhance_result["binary"]
            session.commit()
            timings["enhance"] = time.perf_counter() - t0

            # ------------------------------------------------------------------ #
            # 5. UPSCALING
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.UPSCALING, job)
            upscale_result = upscale_if_needed(enhanced)
            upscaled_image = upscale_result["image"]
            # Un-enhanced variant for the multi-variant ID search (PRD §14).
            raw_upscaled_image = upscale_if_needed(oriented)["image"]
            document.upscaled = upscale_result["upscaled"]
            document.upscale_factor = upscale_result["factor"]
            session.commit()
            timings["upscale"] = time.perf_counter() - t0
            logger.info("Upscale: factor=%.2f upscaled=%s", upscale_result["factor"], upscale_result["upscaled"])

            # ------------------------------------------------------------------ #
            # 6. DETECTING_TEXT
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.DETECTING_TEXT, job)
            # Try OCR data-driven detection first if tesseract is available
            ocr_data = None
            if hasattr(ocr_backend, "_pytesseract") or settings.ocr_engine == "tesseract":
                try:
                    import pytesseract
                    rgb = cv2.cvtColor(upscaled_image, cv2.COLOR_BGR2RGB) if len(upscaled_image.shape) == 3 else cv2.cvtColor(upscaled_image, cv2.COLOR_GRAY2RGB)
                    ocr_data = pytesseract.image_to_data(rgb, output_type=pytesseract.Output.DICT)
                except Exception:
                    ocr_data = None
            text_result = detect_text_regions(upscaled_image, ocr_data=ocr_data)
            session.commit()
            timings["text"] = time.perf_counter() - t0
            logger.info("Text regions: %d candidates", len(text_result["boxes"]))

            # ------------------------------------------------------------------ #
            # 7. RECOGNIZING_ID
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.RECOGNIZING_ID, job)
            id_search = search_id_candidates(
                upscaled_image,
                ocr_backend,
                regions=text_result,
                # PRD §14: enhancement can degrade small header text on difficult
                # photos, so also search the un-enhanced variant and compare.
                extra_images=[raw_upscaled_image],
            )
            candidates = id_search["candidates"]
            ocr_text = " ".join(c["raw"] for c in candidates) if candidates else ""
            # The confidence of the best ID candidate drives auto-accept.
            ocr_confidence = max((c["confidence"] for c in candidates), default=0.0)
            document.ocr_raw = ocr_text or None
            document.ocr_confidence = ocr_confidence
            session.commit()
            timings["ocr"] = time.perf_counter() - t0
            logger.info(
                "ID search: %d candidate(s) [%s] best=%s conf=%.2f",
                len(candidates), ",".join(id_search["strategies"]), id_search["best"], ocr_confidence,
            )

            # ------------------------------------------------------------------ #
            # 8. VALIDATING_ID
            # ------------------------------------------------------------------ #
            t0 = time.perf_counter()
            _update_status(session, document, ProcessingStatus.VALIDATING_ID, job)
            document.ocr_candidates = candidates if candidates else None

            # Compute quality score before validation
            quality_result = compute_quality(upscaled_image, paper_result["confidence"], ocr_confidence)
            document.quality_score = quality_result["quality_score"]
            session.commit()

            validation = validate_id(
                candidates,
                master_ids,
                ocr_confidence,
                paper_result["confidence"],
                quality_result["quality_score"],
            )
            timings["validate"] = time.perf_counter() - t0
            logger.info("Validation: decision=%s final_id=%s reason=%s", validation["decision"], validation["final_id"], validation["reason"])

            # ------------------------------------------------------------------ #
            # 9. FINALIZING -> terminal
            # ------------------------------------------------------------------ #
            _update_status(session, document, ProcessingStatus.FINALIZING, job)
            document.processed_at = datetime_now()

            if validation["decision"] == "COMPLETED":
                final_id = validation["final_id"]
                if not final_id:
                    raise ProcessingError("COMPLETED decision but no final_id", stage="finalize")
                document.idsubsls = final_id
                map_key = _safe_upload_map(upscaled_image, final_id)
                preview_key = _safe_upload_preview(upscaled_image, final_id)
                document.final_object_key = map_key
                document.preview_object_key = preview_key
                document.final_width = upscaled_image.shape[1]
                document.final_height = upscaled_image.shape[0]
                document.review_reason = None
                _update_status(session, document, ProcessingStatus.COMPLETED, job)

                # Update linked wss_target
                target = session.execute(
                    select(WssTarget).where(WssTarget.idsubsls == final_id)
                ).scalar_one_or_none()
                if target:
                    target.status = TargetStatus.COMPLETED
                    target.map_document_id = document.id
                    session.commit()

                return {
                    "decision": "COMPLETED",
                    "document_id": str(document_id),
                    "idsubsls": final_id,
                    "details": {"timings": timings, "quality": quality_result["metrics"]},
                }

            if validation["decision"] == "NEEDS_REVIEW":
                review_key = _safe_upload_review(upscaled_image, str(document.id))
                document.review_object_key = review_key
                document.review_reason = validation["reason"]
                document.final_object_key = None
                document.preview_object_key = None
                _update_status(session, document, ProcessingStatus.NEEDS_REVIEW, job)

                # Update linked target if we have a candidate
                if validation["final_id"]:
                    target = session.execute(
                        select(WssTarget).where(WssTarget.idsubsls == validation["final_id"])
                    ).scalar_one_or_none()
                    if target:
                        target.status = TargetStatus.NEEDS_REVIEW
                        target.map_document_id = document.id
                        session.commit()

                return {
                    "decision": "NEEDS_REVIEW",
                    "document_id": str(document_id),
                    "reason": validation["reason"],
                    "details": {"timings": timings, "quality": quality_result["metrics"]},
                }

            # FAILED
            document.error_message = validation["reason"]
            document.processing_attempts = document.processing_attempts + 1
            _update_status(session, document, ProcessingStatus.FAILED, job)
            return {
                "decision": "FAILED",
                "document_id": str(document_id),
                "reason": validation["reason"],
                "details": {"timings": timings},
            }

    except ProcessingError as exc:
        logger.error("Processing failed at stage %s: %s", exc.stage, exc.message)
        with session_scope() as session:
            document = session.execute(
                select(MapDocument).where(MapDocument.id == document_id)
            ).scalar_one_or_none()
            if document:
                document.processing_status = ProcessingStatus.FAILED
                document.error_message = exc.message
                document.processing_attempts = document.processing_attempts + 1
                session.commit()
        return {"decision": "FAILED", "document_id": str(document_id), "reason": exc.message, "stage": exc.stage}
    except Exception as exc:
        logger.exception("Unexpected error processing document %s", document_id)
        with session_scope() as session:
            document = session.execute(
                select(MapDocument).where(MapDocument.id == document_id)
            ).scalar_one_or_none()
            if document:
                document.processing_status = ProcessingStatus.FAILED
                document.error_message = str(exc)
                document.processing_attempts = document.processing_attempts + 1
                session.commit()
        return {"decision": "FAILED", "document_id": str(document_id), "reason": str(exc)}
    finally:
        # Clean temp dir
        try:
            import shutil
            shutil.rmtree(tmp_base, ignore_errors=True)
            logger.debug("Cleaned temp dir %s", tmp_base)
        except Exception as exc:
            logger.warning("Failed to clean temp dir %s: %s", tmp_base, exc)


def datetime_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)
