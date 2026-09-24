"""Quality scoring: weighted aggregate of paper, OCR, resolution, blur, and contrast."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from wss_common import settings

logger = logging.getLogger(__name__)


def compute_quality(
    image: np.ndarray,
    paper_confidence: float,
    ocr_confidence: float,
) -> dict[str, Any]:
    """Compute a quality score in [0, 1].

    Factors:
        - paper_confidence (30%)
        - ocr_confidence (30%)
        - resolution: min(h, w) relative to upscale threshold (15%)
        - blur: variance of Laplacian normalized (15%)
        - contrast: standard deviation of grayscale normalized (10%)
    """
    if image is None or image.size == 0:
        return {"quality_score": 0.0, "metrics": {}}

    h, w = image.shape[:2]
    short_side = min(h, w)

    # Resolution score
    resolution_score = min(1.0, short_side / settings.upscale_min_short_side)

    # Blur score (variance of Laplacian)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    # Heuristic: 500+ variance is sharp, <100 is blurry
    blur_score = min(1.0, lap_var / 500.0)

    # Contrast score (std dev normalized)
    contrast = np.std(gray)
    contrast_score = min(1.0, contrast / 80.0)

    # Weighted aggregate
    quality_score = (
        0.30 * paper_confidence
        + 0.30 * ocr_confidence
        + 0.15 * resolution_score
        + 0.15 * blur_score
        + 0.10 * contrast_score
    )
    quality_score = max(0.0, min(1.0, quality_score))

    metrics = {
        "resolution_score": round(resolution_score, 4),
        "blur_score": round(blur_score, 4),
        "contrast_score": round(contrast_score, 4),
        "laplacian_variance": round(float(lap_var), 2),
        "short_side": short_side,
    }

    return {"quality_score": quality_score, "metrics": metrics}
