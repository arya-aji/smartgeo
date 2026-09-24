"""Compare two photos that should show the same sheet after rotation correction.

Reports the detected paper corners, the warped size, and the pixel difference
between the two warped images (after rotating A and resizing B to A's size).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from cv_worker.pipeline.paper import detect_paper  # noqa: E402
from cv_worker.pipeline.perspective import correct_perspective  # noqa: E402


def warp(path: str):
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    paper = detect_paper(image)
    warped = correct_perspective(image, paper["corners"])["image"] if paper["corners"] else image
    return warped, paper, image.shape


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--rot-a", type=int, default=180)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    a, paper_a, shape_a = warp(args.a)
    b, paper_b, shape_b = warp(args.b)
    if args.rot_a == 180:
        a = cv2.rotate(a, cv2.ROTATE_180)
    elif args.rot_a == 90:
        a = cv2.rotate(a, cv2.ROTATE_90_CLOCKWISE)

    print(f"A {args.a}: original={shape_a} warped={a.shape[1]}x{a.shape[0]} "
          f"paper_conf={paper_a['confidence']:.2f} method={paper_a['method']}")
    print(f"  corners={paper_a['corners']}")
    print(f"B {args.b}: original={shape_b} warped={b.shape[1]}x{b.shape[0]} "
          f"paper_conf={paper_b['confidence']:.2f} method={paper_b['method']}")
    print(f"  corners={paper_b['corners']}")

    b_resized = cv2.resize(b, (a.shape[1], a.shape[0]))
    diff = cv2.absdiff(a, b_resized)
    print(f"warped size match: {a.shape == b.shape}")
    print(f"mean abs diff: {float(diff.mean()):.1f}  max: {int(diff.max())}  "
          f"pct pixels >30: {float((diff.max(axis=2) > 30).mean() * 100):.2f}%")

    # Where is the top-right header (where the ID lives)?
    h, w = a.shape[:2]
    print(f"top-right quadrant (w/2..w, 0..h/4) of A mean={a[: h // 4, w // 2 :].mean():.0f} "
          f"of B mean={b_resized[: h // 4, w // 2 :].mean():.0f}")

    if args.out:
        cv2.imwrite(args.out + "_a.jpg", a)
        cv2.imwrite(args.out + "_b.jpg", b_resized)
        print(f"saved {args.out}_a.jpg / {args.out}_b.jpg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
