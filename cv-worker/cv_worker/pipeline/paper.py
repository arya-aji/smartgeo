"""Paper detection: find the largest quadrilateral contour in a scanned map image."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def detect_paper(image: np.ndarray) -> dict[str, Any]:
    """Detect paper boundaries in *image* (BGR or grayscale).

    Returns a dict with keys:
        - corners: list of four (x, y) points in order [tl, tr, br, bl] or None
        - confidence: float in [0, 1]
        - method: str describing which heuristic succeeded
    """
    if image is None or image.size == 0:
        return {"corners": None, "confidence": 0.0, "method": "empty"}

    h, w = image.shape[:2]
    area_total = h * w

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return _fallback_full_frame(h, w)

    # Try to find a 4-point convex quad maximizing area
    best_quad: np.ndarray | None = None
    best_area = 0.0

    for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            area = cv2.contourArea(approx)
            if area > best_area:
                best_area = area
                best_quad = approx.reshape(4, 2)

    if best_quad is not None:
        ratio = best_area / area_total
        aspect = _aspect_ratio(best_quad)
        # Sane aspect: between 0.3 and 3.0, area ratio >= 0.15
        if ratio >= 0.15 and 0.3 <= aspect <= 3.0:
            corners = _order_points(best_quad)
            confidence = min(1.0, ratio / 0.5)  # scale so 0.5 area = 1.0 conf
            return {"corners": corners, "confidence": confidence, "method": "approxPolyDP"}

    # Fallback 1: minAreaRect
    largest = max(contours, key=cv2.contourArea)
    rect = cv2.minAreaRect(largest)
    box = cv2.boxPoints(rect)
    box = np.intp(box)
    area = cv2.contourArea(box)
    ratio = area / area_total
    aspect = _aspect_ratio(box)
    if ratio >= 0.15 and 0.3 <= aspect <= 3.0:
        corners = _order_points(box)
        confidence = min(1.0, ratio / 0.5) * 0.85
        return {"corners": corners, "confidence": confidence, "method": "minAreaRect"}

    # Fallback 2: full frame
    return _fallback_full_frame(h, w)


def _fallback_full_frame(h: int, w: int) -> dict[str, Any]:
    corners = [(0, 0), (w - 1, 0), (w - 1, h - 1), (0, h - 1)]
    return {"corners": corners, "confidence": 0.3, "method": "full_frame"}


def _order_points(pts: np.ndarray) -> list[tuple[int, int]]:
    """Order points as [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return [(int(x), int(y)) for x, y in rect]


def _aspect_ratio(pts: np.ndarray) -> float:
    """Compute aspect ratio of a quadrilateral from edge lengths."""
    pts = pts.reshape(-1, 2).astype(np.float32)
    if len(pts) < 4:
        return 1.0
    # Use the two longest edges as width/height approximations
    edges = [np.linalg.norm(pts[i] - pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    w = max(edges[0], edges[2])
    h = max(edges[1], edges[3])
    if h == 0:
        return 999.0
    return w / h
