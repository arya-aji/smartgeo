"""Text region detection: find candidate ID regions without fixed positions."""

from __future__ import annotations

import logging
import re
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def detect_text_regions(image: np.ndarray, ocr_data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Find candidate ID regions in *image*.

    If *ocr_data* (pytesseract image_to_data output) is provided, filter word
    boxes for digit-heavy tokens of length 12-18. Otherwise use contour/connected
    component fallback.

    Returns dict with:
        - crops: list of cropped candidate images
        - boxes: list of (x, y, w, h) bounding boxes in original coordinates
    """
    if image is None or image.size == 0:
        return {"crops": [], "boxes": []}

    h, w = image.shape[:2]
    candidates: list[tuple[int, int, int, int]] = []

    if ocr_data is not None:
        candidates = _from_ocr_data(ocr_data, w, h)

    if not candidates:
        candidates = _from_contours(image)

    crops = []
    boxes = []
    for x, y, bw, bh in candidates:
        x = max(0, x)
        y = max(0, y)
        x2 = min(w, x + bw)
        y2 = min(h, y + bh)
        if x2 > x and y2 > y:
            crop = image[y:y2, x:x2]
            crops.append(crop)
            boxes.append((x, y, x2 - x, y2 - y))

    return {"crops": crops, "boxes": boxes}


def _from_ocr_data(ocr_data: dict[str, Any], img_w: int, img_h: int) -> list[tuple[int, int, int, int]]:
    """Filter pytesseract image_to_data DataFrame-like dict for digit-heavy tokens."""
    candidates = []
    n_boxes = len(ocr_data.get("text", []))
    for i in range(n_boxes):
        text = str(ocr_data["text"][i]).strip()
        if not text:
            continue
        conf = int(ocr_data.get("conf", [0] * n_boxes)[i])
        if conf < 30:
            continue
        length = len(text)
        if not (12 <= length <= 18):
            continue
        digit_ratio = sum(1 for c in text if c.isdigit()) / length
        if digit_ratio < 0.5:
            continue
        x = int(ocr_data["left"][i])
        y = int(ocr_data["top"][i])
        w = int(ocr_data["width"][i])
        h = int(ocr_data["height"][i])
        # Pad slightly
        pad = max(4, int(0.1 * h))
        candidates.append((x - pad, y - pad, w + pad * 2, h + pad * 2))
    return candidates


def _from_contours(image: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Fallback connected-component detection for text-like regions."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Morphological close to group characters into words/lines
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(closed, connectivity=8)
    candidates = []
    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        if area < 100:
            continue
        aspect = w / h if h > 0 else 999
        # Text-like aspect ratio
        if not (2.0 <= aspect <= 20.0):
            continue
        candidates.append((x, y, w, h))
    return candidates
