"""Dump warped + rotated views of map photos (for ground-truth inspection)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from cv_worker.pipeline.paper import detect_paper  # noqa: E402
from cv_worker.pipeline.perspective import correct_perspective  # noqa: E402

ROT = {
    0: None,
    90: cv2.ROTATE_90_CLOCKWISE,
    180: cv2.ROTATE_180,
    270: cv2.ROTATE_90_COUNTERCLOCKWISE,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rots", default="0,180")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rots = [int(r) for r in args.rots.split(",")]
    only = {o.strip() for o in args.only.split(",") if o.strip()}

    for path in sorted(Path(args.dir).iterdir()):
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        if only and path.name not in only:
            continue
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        paper = detect_paper(image)
        warped = correct_perspective(image, paper["corners"])["image"] if paper["corners"] else image
        for deg in rots:
            view = cv2.rotate(warped, ROT[deg]) if ROT[deg] is not None else warped
            target = out / f"{path.stem}_rot{deg}.jpg"
            cv2.imwrite(str(target), view, [cv2.IMWRITE_JPEG_QUALITY, 92])
            print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
