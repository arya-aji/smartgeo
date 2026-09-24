"""Focused probe: try many OCR strategies on a single warped image region set."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import pytesseract  # noqa: E402
from PIL import Image  # noqa: E402

from wss_common import settings  # noqa: E402

from cv_worker.pipeline.normalize_id import normalize_id  # noqa: E402
from cv_worker.pipeline.paper import detect_paper  # noqa: E402
from cv_worker.pipeline.perspective import correct_perspective  # noqa: E402

ROT = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def ocr(img, psm: int) -> str:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    config = f"--psm {psm} -c tessedit_char_whitelist={settings.ocr_whitelist}"
    return pytesseract.image_to_string(Image.fromarray(rgb), config=config).strip()


def scan(name: str, img, psm: int) -> None:
    text = ocr(img, psm)
    found = normalize_id(text)
    flag = f"  <== ID {found['best']}" if found["best"] else ""
    print(f"    {name:<28} psm={psm:<3} id={str(found['best']):<18}{flag}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--rot", type=int, default=0)
    args = ap.parse_args()

    image = cv2.imread(args.image, cv2.IMREAD_COLOR)
    paper = detect_paper(image)
    warped = correct_perspective(image, paper["corners"])["image"] if paper["corners"] else image
    if ROT[args.rot] is not None:
        warped = cv2.rotate(warped, ROT[args.rot])
    h, w = warped.shape[:2]
    print(f"image={args.image} rot={args.rot} warped={w}x{h}")

    for psm in (3, 4, 6, 11, 12, 13):
        scan("whole", warped, psm)

    for rows, cols in ((2, 2), (3, 3), (1, 3), (2, 3)):
        for psm in (6, 11):
            for r in range(rows):
                for c in range(cols):
                    tile = warped[h * r // rows:h * (r + 1) // rows, w * c // cols:w * (c + 1) // cols]
                    scan(f"tile {rows}x{cols} r{r}c{c}", tile, psm)

    for frac, label in ((0.25, "top25"), (0.35, "top35"), (0.5, "top50")):
        for psm in (6, 7, 11):
            scan(f"{label}", warped[: int(h * frac)], psm)

    return 0


if __name__ == "__main__":
    sys.exit(main())
