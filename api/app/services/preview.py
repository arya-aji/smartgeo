"""WebP preview generation from a source image in S3."""

from __future__ import annotations

import io
import logging

from PIL import Image

from wss_common import storage
from wss_common.config import settings

logger = logging.getLogger(__name__)


def generate_preview(source_key: str, dest_key: str) -> None:
    try:
        response = storage.get_s3_client().get_object(
            Bucket=settings.s3_bucket,
            Key=source_key,
        )
        data = response["Body"].read()
        img = Image.open(io.BytesIO(data))

        buf = io.BytesIO()
        img.save(buf, format="WEBP")

        storage.upload_bytes(buf.getvalue(), dest_key, content_type="image/webp")
    except Exception as exc:
        logger.error("Preview generation failed: %s", exc)
        raise
