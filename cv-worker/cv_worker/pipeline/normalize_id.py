"""ID normalization: map confusables and extract candidates matching the ID pattern."""

from __future__ import annotations

import logging
import re
from typing import Any

from wss_common import settings

logger = logging.getLogger(__name__)

# Confusable mapping: OCR-common misreads -> digits
_CONFUSABLES = str.maketrans({
    "O": "0", "o": "0",
    "I": "1", "l": "1", "|": "1",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2", "z": "2",
    "G": "6",
})


def normalize_id(text: str) -> dict[str, Any]:
    """Normalize OCR text and extract ID candidates.

    Returns dict with:
        - candidates: list of dicts {text, confidence, source}
        - best: best candidate string or None
    """
    if not text:
        return {"candidates": [], "best": None}

    # Apply confusable mapping
    normalized = text.translate(_CONFUSABLES)

    # Extract substrings matching the configured pattern.
    # The setting may contain anchors (^$); strip them for substring search.
    raw_pattern = settings.id_pattern
    stripped = raw_pattern.lstrip("^").rstrip("$")
    pattern = re.compile(stripped)
    matches = list(pattern.finditer(normalized))

    candidates = []
    for m in matches:
        candidate = m.group()
        candidates.append({
            "text": candidate,
            "confidence": 0.8,  # base confidence after normalization
            "source": text,
        })

    # If no pattern match, also keep the fully normalized string if it looks close
    if not candidates:
        digits_only = re.sub(r"\D", "", normalized)
        if len(digits_only) == settings.id_length:
            candidates.append({
                "text": digits_only,
                "confidence": 0.5,
                "source": text,
            })

    best = candidates[0]["text"] if candidates else None
    return {"candidates": candidates, "best": best}
