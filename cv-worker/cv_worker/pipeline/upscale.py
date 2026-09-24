"""Upscale small images to improve OCR accuracy."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from wss_common import settings

logger = logging.getLogger(__name__)


def upscale_if_needed(image: np.ndarray) -> dict[str, Any]:
    """Upscale *image* if its short side is below threshold.

    Returns dict with:
        - image: original or upscaled image
        - upscaled: bool
        - factor: float scale factor applied (1.0 if not upscaled)
    """
    if image is None or image.size == 0:
        raise ValueError("Empty image")

    h, w = image.shape[:2]
    short_side = min(h, w)
    min_short = settings.upscale_min_short_side
    max_factor = settings.upscale_max_factor

    if short_side >= min_short:
        return {"image": image.copy(), "upscaled": False, "factor": 1.0}

    factor = min(max_factor, min_short / short_side)
    new_w = int(w * factor)
    new_h = int(h * factor)

    # Use INTER_LANCZOS4 for upscaling, fallback to INTER_CUBIC
    if factor <= 2.0:
        interp = cv2.INTER_LANCZOS4
    else:
        interp = cv2.INTER_CUBIC

    upscaled = cv2.resize(image, (new_w, new_h), interpolation=interp)
    return {"image": upscaled, "upscaled": True, "factor": factor}
