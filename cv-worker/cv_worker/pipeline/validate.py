"""Validation logic: match OCR candidates against master IDs using exact/fuzzy matching."""

from __future__ import annotations

import logging
from typing import Any

from rapidfuzz import process

from wss_common import settings

logger = logging.getLogger(__name__)


def validate_id(
    candidates: list[dict[str, Any]],
    master_ids: set[str],
    ocr_confidence: float,
    paper_confidence: float,
    quality_score: float,
) -> dict[str, Any]:
    """Validate OCR candidates against the master ID list.

    Decision table (ARCHITECTURE.md §9):
    - Exact match + conf >= OCR_AUTO_ACCEPT_CONFIDENCE -> COMPLETED
    - Fuzzy match ratio >= FUZZY_AUTO_ACCEPT_RATIO + conf >= auto threshold -> COMPLETED
    - Confidence in review band, fuzzy in review band, or ID not in master -> NEEDS_REVIEW
    - Paper detection below PAPER_MIN_CONFIDENCE or corrupt -> FAILED

    Returns dict with:
        - decision: "COMPLETED", "NEEDS_REVIEW", or "FAILED"
        - final_id: best matched ID or None
        - reason: human-readable reason
        - candidates: enriched candidate list with match info
    """
    if not candidates:
        return {
            "decision": "NEEDS_REVIEW",
            "final_id": None,
            "reason": "No ID candidates extracted",
            "candidates": [],
        }

    # Paper/quality gate
    if paper_confidence < settings.paper_min_confidence:
        return {
            "decision": "FAILED",
            "final_id": None,
            "reason": f"Paper confidence {paper_confidence:.2f} below threshold {settings.paper_min_confidence}",
            "candidates": candidates,
        }

    if quality_score < settings.quality_min_score:
        return {
            "decision": "NEEDS_REVIEW",
            "final_id": None,
            "reason": f"Quality score {quality_score:.2f} below threshold {settings.quality_min_score}",
            "candidates": candidates,
        }

    best_candidate = None
    best_score = 0.0
    best_match = None
    best_ratio = 0.0

    for cand in candidates:
        text = cand.get("text", "")
        if not text:
            continue

        # Exact match
        if text in master_ids:
            if ocr_confidence >= settings.ocr_auto_accept_confidence:
                return {
                    "decision": "COMPLETED",
                    "final_id": text,
                    "reason": "Exact master match with high confidence",
                    "candidates": candidates,
                }
            # Exact but low confidence -> still strong signal
            if best_candidate is None:
                best_candidate = text
                best_score = 1.0
                best_match = text
                best_ratio = 1.0
            continue

        # Fuzzy match
        if master_ids:
            result = process.extractOne(text, list(master_ids))
            if result:
                match, ratio, _ = result
                ratio_float = float(ratio) / 100.0
                if ratio_float > best_ratio:
                    best_candidate = text
                    best_score = cand.get("confidence", 0.5)
                    best_match = match
                    best_ratio = ratio_float

    # Decision based on best fuzzy match
    if best_match and best_ratio >= settings.fuzzy_auto_accept_ratio and ocr_confidence >= settings.ocr_auto_accept_confidence:
        return {
            "decision": "COMPLETED",
            "final_id": best_match,
            "reason": f"Fuzzy auto-accept ({best_ratio:.2%}) with high OCR confidence",
            "candidates": candidates,
        }

    if best_match and best_ratio >= settings.fuzzy_review_ratio and ocr_confidence >= settings.ocr_review_confidence:
        return {
            "decision": "NEEDS_REVIEW",
            "final_id": best_candidate,
            "reason": f"Fuzzy match in review band ({best_ratio:.2%})",
            "candidates": candidates,
        }

    if ocr_confidence < settings.ocr_review_confidence:
        return {
            "decision": "NEEDS_REVIEW",
            "final_id": best_candidate,
            "reason": f"OCR confidence {ocr_confidence:.2f} below review threshold",
            "candidates": candidates,
        }

    if best_match and best_ratio >= settings.fuzzy_review_ratio:
        return {
            "decision": "NEEDS_REVIEW",
            "final_id": best_candidate,
            "reason": f"Low fuzzy match ratio ({best_ratio:.2%})",
            "candidates": candidates,
        }

    return {
        "decision": "NEEDS_REVIEW",
        "final_id": best_candidate,
        "reason": "ID not found in master list",
        "candidates": candidates,
    }
