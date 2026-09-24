"""Storage I/O helpers for the CV worker.

Wraps wss_common.storage with worker-specific upload/download logic.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

from wss_common import settings
from wss_common.storage import download_file, upload_bytes, upload_file

logger = logging.getLogger(__name__)


def fetch_original(object_key: str, tmp_dir: Path) -> np.ndarray:
    """Download an original image from Garage and load it as a BGR numpy array."""
    local_path = tmp_dir / "original"
    download_file(object_key, local_path)
    image = cv2.imread(str(local_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Unable to decode image from {object_key}")
    return image


def save_image(image: np.ndarray, path: Path, quality: int = 95) -> None:
    """Save a BGR image to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError(f"Failed to write image to {path}")


def upload_map(image: np.ndarray, idsubsls: str) -> str:
    """Upload the final cleaned map as JPEG to maps/{idsubsls}.jpg."""
    from wss_common.storage import maps_key

    key = maps_key(idsubsls)
    _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    upload_bytes(buf.tobytes(), key, content_type="image/jpeg")
    logger.info("Uploaded map %s", key)
    return key


def upload_preview(image: np.ndarray, idsubsls: str, max_dim: int = 400) -> str:
    """Upload a small WebP preview to preview/{idsubsls}.webp."""
    from wss_common.storage import preview_key

    h, w = image.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    key = preview_key(idsubsls)
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    buf = io.BytesIO()
    pil.save(buf, format="WEBP", quality=80, method=6)
    upload_bytes(buf.getvalue(), key, content_type="image/webp")
    logger.info("Uploaded preview %s", key)
    return key


def upload_review(image: np.ndarray, document_id: str) -> str:
    """Upload a review copy to review/{document_id}.jpg."""
    from wss_common.storage import review_key

    key = review_key(document_id)
    _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
    upload_bytes(buf.tobytes(), key, content_type="image/jpeg")
    logger.info("Uploaded review %s", key)
    return key
