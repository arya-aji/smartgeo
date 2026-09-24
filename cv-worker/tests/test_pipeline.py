"""Pipeline module tests (offline, synthetic images)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from cv_worker.pipeline.enhance import enhance_image
from cv_worker.pipeline.normalize_id import normalize_id
from cv_worker.pipeline.orientation import detect_orientation
from cv_worker.pipeline.paper import detect_paper
from cv_worker.pipeline.perspective import correct_perspective
from cv_worker.pipeline.quality import compute_quality
from cv_worker.pipeline.upscale import upscale_if_needed


def test_paper_detects_quad(synthetic_map: np.ndarray) -> None:
    result = detect_paper(synthetic_map)
    assert result["corners"] is not None
    assert len(result["corners"]) == 4
    assert result["confidence"] > 0.15
    assert result["method"] in ("approxPolyDP", "minAreaRect", "full_frame")


def test_perspective_produces_rectangular_output(synthetic_map: np.ndarray) -> None:
    paper = detect_paper(synthetic_map)
    assert paper["corners"] is not None
    result = correct_perspective(synthetic_map, paper["corners"])
    warped = result["image"]
    assert warped.shape[0] > 0
    assert warped.shape[1] > 0
    assert result["matrix"] is not None
    assert len(result["matrix"]) == 3
    assert len(result["matrix"][0]) == 3


def test_orientation_returns_valid_degrees(synthetic_map: np.ndarray) -> None:
    result = detect_orientation(synthetic_map)
    assert result["degrees"] in {0, 90, 180, 270}
    assert result["image"] is not None
    assert result["score"] >= 0.0


def test_enhance_returns_images(synthetic_map: np.ndarray) -> None:
    result = enhance_image(synthetic_map)
    assert "enhanced" in result
    assert "binary" in result
    assert result["enhanced"].shape == synthetic_map.shape
    assert len(result["binary"].shape) == 2


def test_upscale_triggers_below_threshold(small_image: np.ndarray) -> None:
    result = upscale_if_needed(small_image)
    assert result["upscaled"] is True
    assert result["factor"] > 1.0
    h, w = result["image"].shape[:2]
    # factor is capped at upscale_max_factor (2.0), so 400x300 -> 800x600
    assert min(h, w) == 600


def test_upscale_skips_large_image() -> None:
    large = np.full((2000, 2000, 3), 128, dtype=np.uint8)
    result = upscale_if_needed(large)
    assert result["upscaled"] is False
    assert result["factor"] == 1.0


def test_normalize_id_maps_confusables() -> None:
    # Exactly 16 confusable characters -> 16 digits (ID pattern is ^\d{16}$).
    # O->0 o->0 l->1 I->1 S->5 s->5 B->8 Z->2 G->6 |->1
    text = "OolISsBZG|OolISs"
    result = normalize_id(text)
    assert result["best"] is not None
    assert result["best"] == "0011558261001155"
    assert len(result["candidates"]) >= 1


def test_normalize_id_extracts_sixteen_digit_pattern() -> None:
    text = "some prefix 1234567890123456 suffix"
    result = normalize_id(text)
    assert result["best"] == "1234567890123456"
    assert any(c["text"] == "1234567890123456" for c in result["candidates"])


def test_quality_computes_score(synthetic_map: np.ndarray) -> None:
    result = compute_quality(synthetic_map, paper_confidence=0.8, ocr_confidence=0.85)
    assert 0.0 <= result["quality_score"] <= 1.0
    assert "metrics" in result
    assert "blur_score" in result["metrics"]


def test_perspective_raises_on_bad_corners(synthetic_map: np.ndarray) -> None:
    with pytest.raises(ValueError):
        correct_perspective(synthetic_map, [(0, 0), (1, 1)])


def test_paper_returns_fallback_for_empty() -> None:
    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    result = detect_paper(empty)
    assert result["method"] == "empty"
    assert result["confidence"] == 0.0


def test_paper_handles_non_quadrilateral_shape() -> None:
    """Regression: the minAreaRect fallback must not use removed NumPy aliases.

    An ellipse does not reduce to a 4-point approximation, so detection falls
    through to the ``cv2.minAreaRect`` path. This previously crashed with
    ``module 'numpy' has no attribute 'int0'`` on NumPy 2.x.
    """
    image = np.full((600, 800, 3), 30, dtype=np.uint8)
    cv2.ellipse(image, (400, 300), (250, 180), 30, 0, 360, (230, 230, 220), -1)
    result = detect_paper(image)
    assert result["corners"] is not None
    assert len(result["corners"]) == 4
    assert result["method"] in ("approxPolyDP", "minAreaRect", "full_frame")


def test_upload_preview_encodes_webp(synthetic_map: np.ndarray, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: preview upload must encode a real WebP buffer.

    Previously this called ``tempfile.BytesIO()`` (does not exist), so every
    worker-side preview upload failed and the dashboard had no thumbnail for
    auto-accepted maps.
    """
    import cv_worker.storage_io as storage_io

    captured: dict = {}

    def fake_upload(data: bytes, key: str, content_type: str | None = None) -> str:
        captured["data"] = data
        captured["key"] = key
        captured["content_type"] = content_type
        return key

    monkeypatch.setattr(storage_io, "upload_bytes", fake_upload)
    key = storage_io.upload_preview(synthetic_map, "3173030005003200")

    assert key == "preview/3173030005003200.webp"
    assert captured["content_type"] == "image/webp"
    assert captured["data"][:4] == b"RIFF"  # WebP container magic


def test_search_id_candidates_uses_stub_backend(synthetic_map: np.ndarray) -> None:
    """The multi-strategy search must surface a valid 16-digit candidate."""
    from cv_worker.pipeline.id_search import search_id_candidates
    from cv_worker.pipeline.ocr import StubBackend

    result = search_id_candidates(synthetic_map, StubBackend())
    assert result["best"] == "1234567890123456"
    assert any(c["text"] == "1234567890123456" for c in result["candidates"])
    assert "region(" in " ".join(result["strategies"])


def test_search_id_candidates_empty_image() -> None:
    from cv_worker.pipeline.id_search import search_id_candidates
    from cv_worker.pipeline.ocr import StubBackend

    result = search_id_candidates(np.zeros((0, 0, 3), dtype=np.uint8), StubBackend())
    assert result["best"] is None
    assert result["candidates"] == []


def test_orientation_rewards_id_signal(synthetic_map: np.ndarray) -> None:
    """A rotation that yields a valid ID must score far above the weak fallback."""
    from cv_worker.pipeline.ocr import StubBackend

    result = detect_orientation(synthetic_map, ocr_backend=StubBackend())
    assert result["degrees"] in {0, 90, 180, 270}
    assert result["score"] >= 10.0
