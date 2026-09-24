"""Probe search_id_candidates: show every candidate and its source."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--upscale", action="store_true")
    ap.add_argument("--rots", default="0,90,180,270")
    args = ap.parse_args()

    backend = get_ocr_backend()
    image = cv2.imread(args.image, cv2.IMREAD_COLOR)
    paper = detect_paper(image)
    warped = correct_perspective(image, paper["corners"])["image"] if paper["corners"] else image
    if args.upscale:
        up = upscale_if_needed(warped)
        warped = up["image"]
        print(f"upscaled={up['upscaled']} factor={up['factor']:.2f} size={warped.shape[1]}x{warped.shape[0]}")

    for deg in [int(d) for d in args.rots.split(",")]:
        rot = cv2.rotate(warped, ROT[deg]) if ROT[deg] is not None else warped
        result = search_id_candidates(rot, backend)
        print(f"\n--- rot {deg}  strategies={result['strategies']}  best={result['best']}")
        for cand in result["candidates"]:
            print(f"      source={cand['source']:<12} text={cand['text']:<18} conf={cand['confidence']:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
