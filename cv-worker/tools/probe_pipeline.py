"""Mirror the production pipeline order and compare enhancement on/off for OCR.

Production OCRs `upscale(enhance(oriented))`. This probe runs the ID search on
both the production input and a raw-upscale input to isolate the effect of the
enhancement stage on ID readability.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from cv_worker.pipeline.enhance import enhance_image  # noqa: E402
from cv_worker.pipeline.id_search import search_id_candidates  # noqa: E402
from cv_worker.pipeline.ocr import get_ocr_backend  # noqa: E402
from cv_worker.pipeline.paper import detect_paper  # noqa: E402
from cv_worker.pipeline.perspective import correct_perspective  # noqa: E402
from cv_worker.pipeline.upscale import upscale_if_needed  # noqa: E402

ROT = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def show(label: str, result: dict, truth: str) -> None:
    print(f"  {label}: best={result['best']} {'<== TRUTH' if result['best'] == truth else ''}")
    for cand in result["candidates"][:6]:
        mark = "  <== TRUTH" if cand["text"] == truth else ""
        print(f"      {cand['source']:<12} {cand['text']:<18} conf={cand['confidence']:.3f}"
              f" n_src={cand.get('n_sources', 1)}{mark}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--rot", type=int, default=0)
    ap.add_argument("--truth", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    backend = get_ocr_backend()
    image = cv2.imread(args.image, cv2.IMREAD_COLOR)
    paper = detect_paper(image)
    warped = correct_perspective(image, paper["corners"])["image"] if paper["corners"] else image
    if ROT[args.rot] is not None:
        warped = cv2.rotate(warped, ROT[args.rot])
    print(f"{args.image} rot={args.rot} truth={args.truth}")

    enhanced = enhance_image(warped)
    up_a = upscale_if_needed(enhanced["enhanced"])["image"]
    show("A production (enhance -> upscale)", search_id_candidates(up_a, backend), args.truth)

    up_b = upscale_if_needed(warped)["image"]
    show("B raw (upscale only)", search_id_candidates(up_b, backend), args.truth)

    bin_img = enhanced["binary"]
    if bin_img.ndim == 2:
        bin_img = cv2.cvtColor(bin_img, cv2.COLOR_GRAY2BGR)
    show("C binary branch", search_id_candidates(upscale_if_needed(bin_img)["image"], backend), args.truth)

    if args.out:
        cv2.imwrite(args.out + "_enhanced.jpg", up_a)
        cv2.imwrite(args.out + "_raw.jpg", up_b)
        print(f"saved {args.out}_enhanced.jpg / {args.out}_raw.jpg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
