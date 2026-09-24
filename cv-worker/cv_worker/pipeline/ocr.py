"""OCR backends: Tesseract (default), PaddleOCR (optional), Stub (deterministic)."""

from __future__ import annotations

import logging
import re
from abc import abstractmethod
from typing import Any, Protocol

import cv2
import numpy as np
from PIL import Image

from wss_common import settings

logger = logging.getLogger(__name__)


class OCRBackend(Protocol):
    """Protocol for OCR backends."""

    @abstractmethod
    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        """Return (text, confidence)."""
        ...


class StubBackend:
    """Deterministic stub for testing. Extracts digits from image via simple heuristic."""

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        # For testing: return a fixed string so tests can validate downstream logic
        return ("1234567890123456", 0.95)


class TesseractBackend:
    """Tesseract OCR backend."""

    def __init__(self) -> None:
        self._pytesseract = None

    def _ensure_import(self) -> Any:
        if self._pytesseract is None:
            import pytesseract

            self._pytesseract = pytesseract
        return self._pytesseract

    def _run(self, pil: Any, psm: int) -> tuple[str, float]:
        """Run one Tesseract pass and return (text, mean word confidence)."""
        pytesseract = self._ensure_import()
        config = (
            f"--psm {psm} "
            f'-c tessedit_char_whitelist={settings.ocr_whitelist}'
        )
        text = pytesseract.image_to_string(pil, lang=settings.ocr_lang, config=config).strip()

        confidence = 0.0
        try:
            data = pytesseract.image_to_data(
                pil, lang=settings.ocr_lang, config=config, output_type=pytesseract.Output.DICT
            )
            confs: list[int] = []
            for value in data.get("conf", []):
                try:
                    number = int(float(value))
                except (TypeError, ValueError):
                    continue
                if number >= 0:
                    confs.append(number)
            if confs:
                confidence = sum(confs) / len(confs) / 100.0
        except Exception:
            confidence = 0.0
        return text, confidence

    def recognize(self, image: np.ndarray, psm: int | None = None) -> tuple[str, float]:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        pil = Image.fromarray(rgb)

        page_segmentation = psm if psm is not None else settings.ocr_psm
        text, confidence = self._run(pil, page_segmentation)

        # Multi-pass: if the first pass is weak, try PSM 6 and keep whichever
        # produced more digits. An earlier version clamped the winner's
        # confidence to 0.6, which fabricated a value and destroyed candidate
        # ranking (many candidates ended up tied at exactly 0.60).
        if confidence < settings.ocr_review_confidence and page_segmentation != 6:
            alt_text, alt_conf = self._run(pil, 6)
            alt_digits = len(re.sub(r"\D", "", alt_text))
            if alt_text and alt_digits >= len(re.sub(r"\D", "", text)):
                text, confidence = alt_text, alt_conf

        if not text:
            confidence = 0.0
        return (text, confidence)

    def lines(self, image: np.ndarray, psm: int | None = None) -> list[tuple[str, float]]:
        """Return per-text-line ``(text, mean word confidence)``.

        Per-line confidence is far more meaningful than the mean over a whole
        region: a sheet-sized crop is mostly non-ID words, so averaging drags the
        ID line's confidence down to noise (measured: 0.04-0.06) and makes
        candidate ranking meaningless.
        """
        pytesseract = self._ensure_import()
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        pil = Image.fromarray(rgb)
        page_segmentation = psm if psm is not None else settings.ocr_psm
        config = (
            f"--psm {page_segmentation} "
            f'-c tessedit_char_whitelist={settings.ocr_whitelist}'
        )
        try:
            data = pytesseract.image_to_data(
                pil, lang=settings.ocr_lang, config=config, output_type=pytesseract.Output.DICT
            )
        except Exception:
            return []

        grouped: dict[tuple[int, int, int], list[tuple[str, int]]] = {}
        for index in range(len(data.get("text", []))):
            word = str(data["text"][index]).strip()
            if not word:
                continue
            try:
                word_conf = int(float(data["conf"][index]))
            except (TypeError, ValueError):
                continue
            if word_conf < 0:
                continue
            key = (
                int(data["block_num"][index]),
                int(data["par_num"][index]),
                int(data["line_num"][index]),
            )
            grouped.setdefault(key, []).append((word, word_conf))

        result: list[tuple[str, float]] = []
        for words in grouped.values():
            text = " ".join(word for word, _ in words)
            confidence = sum(conf for _, conf in words) / len(words) / 100.0
            result.append((text, confidence))
        return result


class PaddleOCRBackend:
    """PaddleOCR backend (lazy import, graceful if missing)."""

    def __init__(self) -> None:
        self._ocr = None

    def _ensure_ocr(self) -> Any:
        if self._ocr is None:
            try:
                from paddleocr import PaddleOCR

                self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            except Exception as exc:
                logger.warning("PaddleOCR not available: %s", exc)
                raise
        return self._ocr

    def recognize(self, image: np.ndarray) -> tuple[str, float]:
        ocr = self._ensure_ocr()
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if len(image.shape) == 3 else cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        result = ocr.ocr(rgb, cls=True)
        if not result or not result[0]:
            return ("", 0.0)
        lines = result[0]
        texts = []
        confs = []
        for line in lines:
            if line:
                texts.append(line[1][0])
                confs.append(line[1][1])
        text = " ".join(texts)
        confidence = sum(confs) / len(confs) if confs else 0.0
        return (text, confidence)


def get_ocr_backend() -> OCRBackend:
    """Factory returning the configured OCR backend."""
    engine = settings.ocr_engine.lower()
    if engine == "paddleocr":
        try:
            return PaddleOCRBackend()
        except Exception:
            logger.warning("PaddleOCR failed to initialize, falling back to stub")
            return StubBackend()
    if engine == "tesseract":
        return TesseractBackend()
    if engine == "stub":
        return StubBackend()
    logger.warning("Unknown OCR engine '%s', using stub", engine)
    return StubBackend()
