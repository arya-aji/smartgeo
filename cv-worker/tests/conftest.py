"""Pytest configuration and shared fixtures for cv-worker tests."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from cv_worker.pipeline.ocr import StubBackend, TesseractBackend


def _is_tesseract_available() -> bool:
    try:
        TesseractBackend().recognize(np.zeros((50, 200, 3), dtype=np.uint8))
        return True
    except Exception:
        return False


@pytest.fixture
def stub_backend() -> StubBackend:
    return StubBackend()


@pytest.fixture
def tmp_dir() -> Path:
    path = Path(tempfile.mkdtemp(prefix="cv_worker_test_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def synthetic_map() -> np.ndarray:
    """Generate a synthetic map image for offline testing.

    Light quad (paper) on dark background with a 16-digit number.
    """
    h, w = 800, 600
    # Dark background
    image = np.full((h, w, 3), 40, dtype=np.uint8)

    # Light paper quad (slightly rotated rectangle)
    pts = np.array([[80, 100], [520, 90], [530, 700], [70, 710]], dtype=np.int32)
    cv2.fillPoly(image, [pts], (220, 220, 210))

    # Draw a 16-digit ID number near top
    id_text = "1234567890123456"
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(image, id_text, (120, 160), font, 1.2, (30, 30, 30), 3, cv2.LINE_AA)

    # Draw some map-like lines
    for i in range(5):
        y = 250 + i * 90
        cv2.line(image, (120, y), (480, y), (80, 80, 80), 2)
        cv2.line(image, (120 + i * 80, 200), (120 + i * 80, 650), (80, 80, 80), 2)

    return image


@pytest.fixture
def small_image() -> np.ndarray:
    """Small image to trigger upscaling."""
    return np.full((400, 300, 3), 128, dtype=np.uint8)


# Reusable skip marker
skip_unless_tesseract = pytest.mark.skipif(
    not _is_tesseract_available(),
    reason="Tesseract not available",
)
