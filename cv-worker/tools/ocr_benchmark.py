"""Offline OCR / orientation benchmark against labelled map photos.

Runs the real pipeline stages (paper detection -> perspective -> text detection
-> OCR -> ID normalization) on the files in a folder and reports, per file:

  * which of the 4 rotations yields the correct IDSUBSLS (orientation signal)
  * the ID read at each rotation
  * which OCR preprocessing variant reads the ID at the correct rotation

Ground truth is supplied via --labels (JSON: {"1.jpeg": "3171..."}).

Usage (from the cv-worker directory):
    python tools/ocr_benchmark.py --dir ../cek --labels labels.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from cv_worker.pipeline.normalize_id import normalize_id  # noqa: E402
from cv_worker.pipeline.ocr import get_ocr_backend  # noqa: E402
from cv_worker.pipeline.paper import detect_paper  # noqa: E402
from cv_worker.pipeline.perspective import correct_perspective  # noqa: E402
from cv_worker.pipeline.text import detect_text_regions  # noqa: E402

ROTATIONS = (0, 90, 180, 270)


def rotate(image: np.ndarray, degrees: int) -> np.ndarray:
    if degrees == 90:
        return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
    if degrees == 180:
        return cv2.rotate(image, cv2.ROTATE_180)
    if degrees == 270:
        return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return image.copy()


def _tesseract_data(image: np.ndarray):
    import pytesseract
    from PIL import Image

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return pytesseract.image_to_data(Image.fromarray(rgb), output_type=pytesseract.Output.DICT)


def preprocess_crop(crop: np.ndarray, variant: str) -> np.ndarray:
    """Apply a named preprocessing variant to a candidate ID crop."""
    out = crop
    if variant.startswith("up"):
        factor = float(variant[2:].split("_")[0])
        out = cv2.resize(out, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
    if "bin" in variant:
        gray = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY) if out.ndim == 3 else out
        _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)
    if "sharp" in variant:
        blur = cv2.GaussianBlur(out, (0, 0), 3)
        out = cv2.addWeighted(out, 1.6, blur, -0.6, 0)
    return out


def detect_regions(image: np.ndarray) -> dict:
    try:
        data = _tesseract_data(image)
    except Exception:
        data = None
    return detect_text_regions(image, ocr_data=data)


def ocr_regions(regions: dict, backend, variant: str = "raw") -> dict:
    best_id, best_conf, texts = None, -1.0, []
    for crop in regions["crops"]:
        try:
            text, conf = backend.recognize(preprocess_crop(crop, variant))
        except Exception:
            continue
        texts.append(text)
        norm = normalize_id(text)
        if norm["best"] and conf > best_conf:
            best_id, best_conf = norm["best"], conf
    return {
        "id": best_id,
        "conf": max(best_conf, 0.0),
        "crops": len(regions["crops"]),
        "text": " ".join(texts)[:60],
    }


def read_id(image: np.ndarray, backend, variant: str = "raw") -> dict:
    """Replicate the processor's OCR step and return the best normalized ID."""
    return ocr_regions(detect_regions(image), backend, variant)


def ocr_whole(image: np.ndarray, psm: int) -> dict:
    """Whole-image OCR at a given PSM, then scan for a 16-digit candidate."""
    import pytesseract
    from PIL import Image

    from wss_common import settings

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    config = f"--psm {psm} -c tessedit_char_whitelist={settings.ocr_whitelist}"
    text = pytesseract.image_to_string(Image.fromarray(rgb), config=config).strip()
    norm = normalize_id(text)
    return {"id": norm["best"], "text": text[:70]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--labels", required=True, help="JSON file mapping filename -> true idsubsls")
    parser.add_argument("--variants", default="raw,up2,up3,bin,up2_bin,up3_bin,up3_sharp")
    parser.add_argument("--only", default="")
    parser.add_argument("--upscale", action="store_true", help="apply adaptive upscaling before OCR")
    args = parser.parse_args()

    labels = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    backend = get_ocr_backend()
    files = sorted(p for p in Path(args.dir).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if args.only:
        wanted = {w.strip() for w in args.only.split(",")}
        files = [f for f in files if f.name in wanted]

    print(f"engine={type(backend).__name__}  files={len(files)}  variants={variants}\n")

    orientation_ok = 0
    orientation_ok_detect = 0
    final_ok = 0
    for path in files:
        truth = labels.get(path.name)
        image = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"{path.name}: cannot decode")
            continue

        paper = detect_paper(image)
        corners = paper["corners"]
        warped = correct_perspective(image, corners)["image"] if corners else image
        warped_base = warped

        if args.upscale:
            from cv_worker.pipeline.upscale import upscale_if_needed

            up = upscale_if_needed(warped)
            warped = up["image"]
            print(f"    upscale: applied={up['upscaled']} factor={up['factor']:.2f} size={warped.shape[1]}x{warped.shape[0]}")

        print(f"--- {path.name}  truth={truth}  paper_conf={paper['confidence']:.2f} ---")

        per_rotation = {}
        for deg in ROTATIONS:
            rot = rotate(warped, deg)
            res = read_id(rot, backend, "raw")
            whole = {psm: ocr_whole(rot, psm) for psm in (6, 11)}
            res["whole"] = whole
            per_rotation[deg] = res
            whole_ids = {psm: (v["id"] or "-") for psm, v in whole.items()}
            correct = truth and (res["id"] == truth or any(v["id"] == truth for v in whole.values()))
            mark = "  <== CORRECT" if correct else ""
            print(f"    rot {deg:>3}: crops_id={str(res['id']):<18} conf={res['conf']:.2f} "
                  f"crops={res['crops']:<3} whole={whole_ids}{mark}")

        hit = [d for d, r in per_rotation.items()
               if truth and (r["id"] == truth or any(v["id"] == truth for v in r["whole"].values()))]
        if hit:
            orientation_ok += 1
            best_rot = hit[0]
        else:
            # fall back to the rotation with the highest confidence for variant testing
            best_rot = max(per_rotation, key=lambda d: per_rotation[d]["conf"])
        print(f"    orientation: {'OK' if hit else 'MISS'} (truth found at {hit or 'none'}; using {best_rot})")

        from cv_worker.pipeline.orientation import detect_orientation

        chosen = detect_orientation(warped_base, ocr_backend=backend, master_ids=set(labels.values()))
        chosen_ok = bool(truth) and chosen["degrees"] in hit
        if chosen_ok:
            orientation_ok_detect += 1
        print(f"    detect_orientation -> {chosen['degrees']}deg score={chosen['score']:.2f} "
              f"{'OK' if chosen_ok else 'MISS'}")

        rotated = rotate(warped, best_rot)
        regions = detect_regions(rotated)
        variant_results = {}
        for variant in variants:
            res = ocr_regions(regions, backend, variant)
            variant_results[variant] = res
            mark = "  <== CORRECT" if truth and res["id"] == truth else ""
            print(f"    variant {variant:<10}: id={str(res['id']):<18} conf={res['conf']:.2f}{mark}")

        if truth and any(r["id"] == truth for r in variant_results.values()):
            final_ok += 1
        print()

    print("=" * 60)
    print(f"orientation correct : {orientation_ok}/{len(files)}")
    print(f"detect_orientation  : {orientation_ok_detect}/{len(files)}")
    print(f"id readable (best)  : {final_ok}/{len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
