"""Promote a review output to a final map + preview."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from wss_common import storage
from wss_common.config import settings
from wss_common.enums import ProcessingStatus, TargetStatus
from wss_common.models import MapDocument, WssTarget

from app.services.preview import generate_preview

logger = logging.getLogger(__name__)


def promote_review_output(db: Session, doc: MapDocument, idsubsls: str) -> None:
    if not doc.review_object_key:
        raise ValueError("Document has no review object key")

    final_key = storage.maps_key(idsubsls)
    preview_key = storage.preview_key(idsubsls)

    try:
        storage.get_s3_client().copy_object(
            Bucket=settings.s3_bucket,
            CopySource={"Bucket": settings.s3_bucket, "Key": doc.review_object_key},
            Key=final_key,
        )
    except Exception as exc:
        logger.error("Failed to copy review to final: %s", exc)
        raise

    try:
        generate_preview(final_key, preview_key)
    except Exception as exc:
        logger.error("Failed to generate preview: %s", exc)
        raise

    doc.final_object_key = final_key
    doc.preview_object_key = preview_key
    doc.idsubsls = idsubsls
    doc.processing_status = ProcessingStatus.COMPLETED
    doc.processed_at = datetime.now(timezone.utc)

    target = db.query(WssTarget).filter(WssTarget.idsubsls == idsubsls).first()
    if target is not None:
        target.status = TargetStatus.COMPLETED
        target.map_document_id = doc.id
    else:
        target = WssTarget(
            idsubsls=idsubsls,
            status=TargetStatus.COMPLETED,
            map_document_id=doc.id,
        )
        db.add(target)
