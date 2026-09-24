"""Validation logic tests (offline, deterministic)."""

from __future__ import annotations

import pytest

from cv_worker.pipeline.validate import validate_id


def _make_candidate(text: str, confidence: float = 0.8) -> dict:
    return {"text": text, "confidence": confidence, "source": text}


class FakeSettings:
    paper_min_confidence = 0.60
    ocr_auto_accept_confidence = 0.90
    ocr_review_confidence = 0.55
    fuzzy_auto_accept_ratio = 0.93
    fuzzy_review_ratio = 0.72
    quality_min_score = 0.50


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    import cv_worker.pipeline.validate as validate_mod
    monkeypatch.setattr(validate_mod, "settings", FakeSettings())


def test_validate_exact_match_high_confidence() -> None:
    master = {"1234567890123456"}
    candidates = [_make_candidate("1234567890123456", confidence=0.95)]
    result = validate_id(candidates, master, ocr_confidence=0.95, paper_confidence=0.8, quality_score=0.8)
    assert result["decision"] == "COMPLETED"
    assert result["final_id"] == "1234567890123456"
    assert "exact" in result["reason"].lower()


def test_validate_fuzzy_auto_accept() -> None:
    master = {"1234567890123456"}
    # One digit off but ratio should be high
    candidates = [_make_candidate("1234567890123457", confidence=0.8)]
    result = validate_id(candidates, master, ocr_confidence=0.95, paper_confidence=0.8, quality_score=0.8)
    assert result["decision"] == "COMPLETED"
    assert result["final_id"] == "1234567890123456"


def test_validate_needs_review_low_confidence() -> None:
    master = {"1234567890123456"}
    candidates = [_make_candidate("1234567890123456", confidence=0.4)]
    result = validate_id(candidates, master, ocr_confidence=0.50, paper_confidence=0.8, quality_score=0.8)
    assert result["decision"] == "NEEDS_REVIEW"
    assert result["final_id"] == "1234567890123456"


def test_validate_needs_review_not_in_master() -> None:
    master = {"9999999999999999"}
    candidates = [_make_candidate("1234567890123456", confidence=0.8)]
    result = validate_id(candidates, master, ocr_confidence=0.95, paper_confidence=0.8, quality_score=0.8)
    assert result["decision"] == "NEEDS_REVIEW"
    assert "not found" in result["reason"].lower() or "master" in result["reason"].lower()


def test_validate_failed_low_paper_confidence() -> None:
    master = {"1234567890123456"}
    candidates = [_make_candidate("1234567890123456", confidence=0.95)]
    result = validate_id(candidates, master, ocr_confidence=0.95, paper_confidence=0.30, quality_score=0.8)
    assert result["decision"] == "FAILED"
    assert "paper" in result["reason"].lower()


def test_validate_needs_review_low_quality() -> None:
    master = {"1234567890123456"}
    candidates = [_make_candidate("1234567890123456", confidence=0.95)]
    result = validate_id(candidates, master, ocr_confidence=0.95, paper_confidence=0.8, quality_score=0.30)
    assert result["decision"] == "NEEDS_REVIEW"
    assert "quality" in result["reason"].lower()


def test_validate_no_candidates() -> None:
    master = {"1234567890123456"}
    result = validate_id([], master, ocr_confidence=0.0, paper_confidence=0.8, quality_score=0.8)
    assert result["decision"] == "NEEDS_REVIEW"
    assert result["final_id"] is None


def test_validate_fuzzy_review_band() -> None:
    master = {"1234567890123456"}
    # Very different ID -> low fuzzy ratio
    candidates = [_make_candidate("0000000000000000", confidence=0.6)]
    result = validate_id(candidates, master, ocr_confidence=0.80, paper_confidence=0.8, quality_score=0.8)
    assert result["decision"] == "NEEDS_REVIEW"
