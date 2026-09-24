"""Robust IDSUBSLS search combining several OCR strategies.

A single OCR pass over text-detected crops misses IDs that sit in a header box,
or that Tesseract fragments at whole-sheet scale. Measured on real photos, the
whole-image coarse-PSM pass recovered IDs that the crop pass could not (e.g. an
upside-down sheet and a blurred sheet), so we combine:

  1. OCR of text-detected candidate crops (position-agnostic)
  2. whole-image OCR at coarse page-segmentation modes (catches header lines)
  3. tile OCR as a last resort, only when nothing was found yet

Every strategy's text is normalized (confusable mapping) and filtered against
the configured ID pattern, so callers get a ranked list of valid 16-digit
candidates with the strategy that produced them.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from .normalize_id import normalize_id
from .text import detect_text_regions

logger = logging.getLogger(__name__)

# Page-segmentation modes that work well for a dense sheet with a header line.
WHOLE_PSMS: tuple[int, ...] = (6, 11)
# Coarse overlapping grids. The IDSUBSLS is a small header line whose readable
# scale varies between captures: measured on real photos, two captures of the
# *same* sheet each required a different crop scale (one read only at
# whole-sheet scale, the other only as a top-third/right-half crop). Overlapping
# grids are therefore run and candidates are ranked by cross-pass consensus.
COARSE_GRIDS: tuple[tuple[int, int], ...] = ((2, 2), (3, 2), (2, 3))
# Finer tiling used only as a last resort.
TILE_GRIDS: tuple[tuple[int, int], ...] = ((1, 3), (2, 3))
TILE_PSM = 6


def _recognize(backend: Any, image: np.ndarray, psm: int | None = None) -> tuple[str, float]:
    """OCR a region, optionally forcing a page-segmentation mode."""
    if psm is not None:
        try:
            return backend.recognize(image, psm=psm)
        except TypeError:
            pass  # backend does not support PSM selection
    try:
        return backend.recognize(image)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("OCR failed on a region: %s", exc)
        return ("", 0.0)


def _collect_region(
    store: dict[str, dict],
    backend: Any,
    image: np.ndarray,
    source: str,
    psm: int | None = None,
) -> None:
    """OCR a region and record candidates with per-line confidence when possible.

    Using per-line confidence (rather than the mean over the whole region) is
    what makes cross-region ranking meaningful: the ID line keeps its own high
    confidence instead of being averaged away by the surrounding map text.
    """
    if hasattr(backend, "lines"):
        try:
            for text, confidence in backend.lines(image, psm=psm):
                _collect(store, text, confidence, source)
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("per-line OCR failed for %s: %s", source, exc)
    text, confidence = _recognize(backend, image, psm=psm)
    _collect(store, text, confidence, source)


def _tesseract_data(image: np.ndarray) -> dict | None:
    try:
        import cv2
        import pytesseract
        from PIL import Image

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return pytesseract.image_to_data(Image.fromarray(rgb), output_type=pytesseract.Output.DICT)
    except Exception:
        return None


def _tiles(image: np.ndarray, rows: int, cols: int) -> list[np.ndarray]:
    h, w = image.shape[:2]
    out: list[np.ndarray] = []
    for r in range(rows):
        for c in range(cols):
            tile = image[h * r // rows : h * (r + 1) // rows, w * c // cols : w * (c + 1) // cols]
            if tile.size:
                out.append(tile)
    return out


def _collect(store: dict[str, dict], text: str, confidence: float, source: str) -> None:
    """Record a candidate, keeping every distinct source that produced it.

    Consensus matters: a genuine ID tends to be read by several independent
    passes, whereas a spurious digit run usually appears in only one.
    """
    if not text:
        return
    found = normalize_id(text)
    for cand in found["candidates"]:
        key = cand["text"]
        entry = store.get(key)
        if entry is None:
            store[key] = {
                "text": key,
                "confidence": float(confidence),
                "source": source,
                "sources": [source],
                "raw": text.strip()[:200],
            }
            continue
        if source not in entry["sources"]:
            entry["sources"].append(source)
        if confidence > entry["confidence"]:
            entry["confidence"] = float(confidence)
            entry["source"] = source
            entry["raw"] = text.strip()[:200]


def _scan(
    store: dict[str, dict],
    strategies: list[str],
    backend: Any,
    image: np.ndarray,
    regions: dict | None,
    tag: str,
) -> None:
    """Run every always-on strategy against one image variant."""
    if regions is None:
        regions = detect_text_regions(image, ocr_data=_tesseract_data(image))
    for crop in regions["crops"]:
        _collect_region(store, backend, crop, f"region{tag}")
    strategies.append(f"region{tag}({len(regions['crops'])})")

    for psm in WHOLE_PSMS:
        _collect_region(store, backend, image, f"whole_psm{psm}{tag}", psm=psm)
        strategies.append(f"whole_psm{psm}{tag}")

    for rows, cols in COARSE_GRIDS:
        for tile in _tiles(image, rows, cols):
            _collect_region(store, backend, tile, f"grid{rows}x{cols}{tag}", psm=TILE_PSM)
        strategies.append(f"grid{rows}x{cols}{tag}")


def search_id_candidates(
    image: np.ndarray,
    backend: Any,
    allow_tiles: bool = True,
    regions: dict | None = None,
    extra_images: list[np.ndarray] | None = None,
) -> dict[str, Any]:
    """Search *image* (and any *extra_images* variants) for IDSUBSLS candidates.

    ``regions`` may be supplied to reuse an already-computed text-detection
    result. ``extra_images`` implements the PRD §14 multi-variant strategy: for
    difficult photos the enhancement stage can degrade small header text, so the
    un-enhanced variant is searched too and results are compared.

    Returns ``{"candidates": [...], "best": str | None, "strategies": [...]}``
    where candidates are ranked by cross-pass consensus then confidence.
    """
    if image is None or image.size == 0:
        return {"candidates": [], "best": None, "strategies": []}

    store: dict[str, dict] = {}
    strategies: list[str] = []

    _scan(store, strategies, backend, image, regions, tag="")
    for index, extra in enumerate(extra_images or [], start=1):
        if extra is not None and extra.size:
            _scan(store, strategies, backend, extra, None, tag=f"_alt{index}")

    # Finer tiling is expensive, so only run it when nothing has been found yet.
    if not store and allow_tiles:
        for rows, cols in TILE_GRIDS:
            for tile in _tiles(image, rows, cols):
                _collect_region(store, backend, tile, f"tile{rows}x{cols}", psm=TILE_PSM)
            strategies.append(f"tile{rows}x{cols}")

    candidates = sorted(
        store.values(),
        key=lambda c: (len(c["sources"]), c["confidence"]),
        reverse=True,
    )
    for cand in candidates:
        cand["n_sources"] = len(cand["sources"])
    return {
        "candidates": candidates,
        "best": candidates[0]["text"] if candidates else None,
        "strategies": strategies,
    }
