"""Perspective correction: warp a quadrilateral to a rectangular top-down view."""

from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def correct_perspective(image: np.ndarray, corners: list[tuple[int, int]]) -> dict[str, Any]:
    """Warp *image* so that *corners* become a rectangle.

    Returns dict with:
        - image: warped BGR image
        - matrix: 3x3 perspective transform matrix as nested list
    """
    if image is None or image.size == 0:
        raise ValueError("Empty image")
    if len(corners) != 4:
        raise ValueError(f"Expected 4 corners, got {len(corners)}")

    ordered = np.array(corners, dtype=np.float32)

    # Compute output size from edge lengths
    tl, tr, br, bl = ordered
    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = int(max(height_a, height_b))

    # Ensure minimum dimensions
    max_width = max(max_width, 1)
    max_height = max(max_height, 1)

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )

    matrix = cv2.getPerspectiveTransform(ordered, dst)
    warped = cv2.warpPerspective(image, matrix, (max_width, max_height))

    return {
        "image": warped,
        "matrix": matrix.tolist(),
    }
