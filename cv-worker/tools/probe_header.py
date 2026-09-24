"""Probe the header region of a map photo at several magnifications.

The IDSUBSLS sits in a small header box, so OCR at whole-sheet scale may fail
while a magnified crop succeeds. This tests crop upscaling + several PSMs.
"""

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
from cv_worker.pipeline.upscale import upscale_if_needed  # noqa: E402

ROT = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def ocr(img, psm: int) -> str:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    config = f"--psm {psm} -c tessedit_char_whitelist={settings.ocr_whitelist}"
    return pytesseract.image_to_string(Image.fromarray(rgb), config=config).strip()


def report(label: str, img, psms=(6, 7, 11, 13)) -> None:
    for psm in psms:
        text = ocr(img, psm)
        found = normalize_id(text)
        if found["best"]:
            print(f"    {label:<26} psm={psm:<3} -> {found['best']}   (raw={text.strip()[:40]!r})")
            return
    print(f"    {label:<26} -> none")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--rot", type=int, default=0)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    image = cv2.imread(args.image, cv2.IMREAD_COLOR)
    paper = detect_paper(image)
    warped = correct_perspective(image, paper["corners"])["image"] if paper["corners"] else image
    if ROT[args.rot] is not None:
        warped = cv2.rotate(warped, ROT[args.rot])
    up = upscale_if_needed(warped)
    img = up["image"]
    h, w = img.shape[:2]
    print(f"{args.image} rot={args.rot} upscaled={up['upscaled']} factor={up['factor']:.2f} size={w}x{h}")

    regions = {
        "top-right quadrant": img[0 : h // 3, w // 2 : w],
        "top strip 25%": img[0 : h // 4, :],
        "top-right 6th": img[0 : h // 4, w * 2 // 3 : w],
        "full": img,
    }
    for name, crop in regions.items():
        if crop.size == 0:
            continue
        for factor in (1, 2, 3, 4):
            scaled = crop if factor == 1 else cv2.resize(crop, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
            report(f"{name} x{factor}", scaled)
            if args.out and factor == 3:
                cv2.imwrite(f"{args.out}_{name.replace(' ', '_')}_x{factor}.jpg", scaled)
    return 0


if __name__ == "__main__":
    sys.exit(main())
