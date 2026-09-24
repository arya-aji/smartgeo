"""Attach presigned object URLs (and uploader name) to response models."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from wss_common import storage
from wss_common.models import MapDocument, User

from app.schemas import MapDocumentDetail

logger = logging.getLogger(__name__)

_DETAIL_URL_FIELDS = (
    ("original_url", "original_object_key"),
    ("final_url", "final_object_key"),
    ("review_url", "review_object_key"),
    ("preview_url", "preview_object_key"),
)


def attach_detail_urls(
    db: Session, doc: MapDocument, detail: MapDocumentDetail
) -> MapDocumentDetail:
    """Fill `uploaded_by_name` and every presigned URL on a MapDocumentDetail."""
    _set_uploaded_by_name(db, doc, detail)
    for field, key_attr in _DETAIL_URL_FIELDS:
        setattr(detail, field, _presign(getattr(doc, key_attr, None)))
    return detail


def attach_summary(db: Session, doc: MapDocument, summary, preview_key: str | None) -> None:
    """Fill `uploaded_by_name` and `preview_url` on a MapDocumentSummary."""
    _set_uploaded_by_name(db, doc, summary)
    summary.preview_url = _presign(preview_key)


def _set_uploaded_by_name(db: Session, doc: MapDocument, target) -> None:
    target.uploaded_by_name = (
        db.query(User.name).filter(User.id == doc.uploaded_by).scalar() if doc.uploaded_by else None
    )


def _presign(key: str | None) -> str | None:
    if not key:
        return None
    try:
        return storage.presign_get(key)
    except Exception as exc:  # noqa: BLE001 - a missing URL must not fail the request
        logger.warning("Could not presign %s: %s", key, exc)
        return None
