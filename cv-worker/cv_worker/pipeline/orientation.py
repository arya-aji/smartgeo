"""Orientation detection: rotate image to readable upright position."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from .id_search import search_id_candidates
from .upscale import upscale_if_needed

logger = logging.getLogger(__name__)


def detect_orientation(
    image: np.ndarray,
    ocr_backend: Any | None = None,
    master_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Try 0/90/180/270 degree rotations and score each.

    If *ocr_backend* is available, each rotation is scored by whether a valid
    IDSUBSLS can be read from it. When *master_ids* is supplied, a rotation whose
    ID matches the master list wins outright — the master list is the domain
    ground truth and is far more reliable than Tesseract confidence on noisy
    photos. Otherwise fall back to a cheap horizontal-text-line heuristic.

    Returns dict with:
        - degrees: best rotation (0, 90, 180, or 270)
        - image: rotated image
        - score: float score (higher is better)
    """
    if image is None or image.size == 0:
        return {"degrees": 0, "image": image, "score": 0.0}

    # Orientation is decided before the pipeline's upscaling stage, but the ID is
    # often only readable at the upscaled resolution (measured on real photos:
    # the correct rotation was invisible pre-upscale). Score on an upscaled copy
    # so the signal matches the conditions OCR will actually run under, while
    # still returning the rotation applied to the original image.
    scoring_image = upscale_if_needed(image)["image"] if ocr_backend is not None else image

    candidates = []
    for deg in (0, 90, 180, 270):
        rotated = _rotate(scoring_image, deg)
        if ocr_backend is not None:
            score = _score_with_ocr(rotated, ocr_backend, master_ids)
        else:
            score = _score_heuristic(rotated)
        candidates.append((deg, score))

    best_deg, best_score = max(candidates, key=lambda item: item[1])
    return {"degrees": best_deg, "image": _rotate(image, best_deg), "score": best_score}


def _rotate(image: np.ndarray, degrees: int) -> np.ndarray:
    if degrees == 0:
        return image.copy()
    if degrees == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image.copy()


def _score_with_ocr(
    image: np.ndarray,
    ocr_backend: Any,
    master_ids: set[str] | None = None,
) -> float:
    """Score a rotation by ID readability, preferring IDs present in the master.

    Tesseract confidence alone is unreliable here: measured on real photos a
    spurious 16-digit read carried a *higher* confidence (0.14-0.25) than the
    genuine ID (0.00), which made confidence-only scoring pick the wrong
    rotation. The master IDSUBSLS list is the domain ground truth, so a rotation
    producing an ID that matches it is treated as decisive.
    """
    try:
        result = search_id_candidates(image, ocr_backend, allow_tiles=False)
    except Exception:
        result = {"candidates": [], "best": None}

    candidates = result.get("candidates") or []
    if not candidates:
        return 0.0
    best_conf = max(float(c["confidence"]) for c in candidates)

    if master_ids:
        for cand in candidates:
            if cand["text"] in master_ids:
                return 100.0 + best_conf
        try:
            from rapidfuzz import process as fuzz_process

            match = fuzz_process.extractOne(candidates[0]["text"], list(master_ids))
            if match is not None:
                return 20.0 * (float(match[1]) / 100.0) + best_conf
        except Exception:
            pass

    return 10.0 + best_conf


def _score_heuristic(image: np.ndarray) -> float:
    """Cheap fallback: horizontal line density via morphological operations."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    # Threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    # Horizontal kernel
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 1))
    h_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel, iterations=2)
    # Vertical kernel
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 25))
    v_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel, iterations=2)
    h_score = np.sum(h_lines > 0)
    v_score = np.sum(v_lines > 0)
    # Prefer orientations with more horizontal than vertical text lines
    if h_score + v_score == 0:
        return 0.0
    return float(h_score) / (h_score + v_score + 1e-6)
