"""Image enhancement: illumination correction, denoising, sharpening, binarization."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def enhance_image(image: np.ndarray) -> dict[str, Any]:
    """Enhance a map image for better OCR while preserving thin lines and small text.

    Returns dict with:
        - enhanced: BGR enhanced image
        - binary: binarized image for OCR
    """
    if image is None or image.size == 0:
        raise ValueError("Empty image")

    # Work on LAB lightness channel for illumination correction
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    # CLAHE on L channel
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_clahe = clahe.apply(l)

    # Background subtraction for uneven illumination
    bg = cv2.GaussianBlur(l_clahe, (51, 51), 0)
    bg = cv2.add(bg, 1)  # avoid div by zero
    l_corrected = cv2.divide(l_clahe, bg, scale=255)

    # Merge back
    lab_enhanced = cv2.merge([l_corrected, a, b])
    enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

    # Mild denoise
    enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 5, 5, 7, 21)

    # Contrast stretch
    enhanced = _contrast_stretch(enhanced)

    # Unsharp mask to sharpen edges without destroying thin lines
    gaussian = cv2.GaussianBlur(enhanced, (0, 0), 3)
    enhanced = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)

    # Binarized variant for OCR
    gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    return {"enhanced": enhanced, "binary": binary}


def _contrast_stretch(image: np.ndarray) -> np.ndarray:
    """Stretch image histogram to full 0-255 range."""
    in_min = np.percentile(image, 1)
    in_max = np.percentile(image, 99)
    if in_max <= in_min:
        return image
    out = (image.astype(np.float32) - in_min) * (255.0 / (in_max - in_min))
    out = np.clip(out, 0, 255)
    return out.astype(np.uint8)
