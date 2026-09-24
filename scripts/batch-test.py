"""Batch-test the processing pipeline against a folder of map photos.

Uploads every image directly to Garage, waits for the CV worker to finish, then
prints a per-file summary (paper confidence, orientation, upscaling, OCR result,
quality, decision and reason).

Usage:
    python scripts/batch-test.py --dir cek --timeout 900
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TERMINAL = {"COMPLETED", "NEEDS_REVIEW", "FAILED"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def _request(
    method: str,
    url: str,
    data: dict | None = None,
    token: str | None = None,
    headers: dict[str, str] | None = None,
    raw: bytes | None = None,
) -> tuple[int, object]:
    hdrs = dict(headers or {})
    if raw is None:
        hdrs.setdefault("Content-Type", "application/json")
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read().decode()
            return resp.status, (json.loads(payload) if payload else None)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise SystemExit(f"HTTP {exc.code} on {method} {url}: {detail}") from exc


def _num(value: object, digits: int = 3) -> str:
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "-"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--dir", required=True)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()

    base = args.api.rstrip("/")
    files = sorted(p for p in Path(args.dir).iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if not files:
        raise SystemExit(f"no images found in {args.dir}")

    _, login = _request("POST", f"{base}/api/auth/login",
                        {"username": args.username, "password": args.password})
    token = login["access_token"]  # type: ignore[index]
    print(f"logged in as {login['user']['username']}")  # type: ignore[index]
    print(f"uploading {len(files)} image(s) from {args.dir}\n")

    docs: list[dict] = []
    for path in files:
        blob = path.read_bytes()
        _, pre = _request("POST", f"{base}/api/uploads/presign",
                          {"filename": path.name, "content_type": "image/jpeg", "size": len(blob)},
                          token=token)
        _request("PUT", pre["upload_url"], headers=pre["headers"], raw=blob)  # type: ignore[index]
        _request("POST", f"{base}/api/uploads/complete",
                 {"map_document_id": pre["map_document_id"], "file_size": len(blob)}, token=token)  # type: ignore[index]
        docs.append({"file": path.name, "id": pre["map_document_id"], "started": time.time()})  # type: ignore[index]
        print(f"  queued {path.name:<10} ({len(blob)//1024} KB) -> {pre['map_document_id']}")  # type: ignore[index]

    print(f"\nwaiting for {len(docs)} job(s) to reach a terminal state...")
    deadline = time.time() + args.timeout
    results: dict[str, dict] = {}
    finished_at: dict[str, float] = {}
    while time.time() < deadline:
        done = 0
        for entry in docs:
            _, doc = _request("GET", f"{base}/api/maps/{entry['id']}", token=token)
            results[entry["file"]] = doc  # type: ignore[index]
            if doc["processing_status"] in TERMINAL:  # type: ignore[index]
                done += 1
                finished_at.setdefault(entry["file"], time.time())
        if done == len(docs):
            break
        time.sleep(5)

    header = (f"{'file':<9} {'status':<13} {'paper':>6} {'orient':>6} {'upsc':>5} "
              f"{'factor':>6} {'ocr':>6} {'qual':>6} {'secs':>5}  ocr_raw")
    print("\n" + header)
    print("-" * (len(header) + 14))
    for entry in docs:
        doc = results.get(entry["file"], {})
        secs = finished_at.get(entry["file"], time.time()) - entry["started"]
        print(f"{entry['file']:<9} {str(doc.get('processing_status')):<13} "
              f"{_num(doc.get('paper_confidence'), 2):>6} {str(doc.get('orientation')):>6} "
              f"{str(doc.get('upscaled')):>5} {_num(doc.get('upscale_factor'), 2):>6} "
              f"{_num(doc.get('ocr_confidence'), 2):>6} {_num(doc.get('quality_score'), 2):>6} "
              f"{secs:>5.1f}  {doc.get('ocr_raw')}")

    print("\ndetail:")
    for entry in docs:
        doc = results.get(entry["file"], {})
        print(f"  {entry['file']:<9} idsubsls={doc.get('idsubsls')} "
              f"reason={doc.get('review_reason')} error={doc.get('error_message')} "
              f"final={doc.get('final_object_key')} review={doc.get('review_object_key')}")

    counts: dict[str, int] = {}
    for entry in docs:
        status = results.get(entry["file"], {}).get("processing_status", "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    print(f"\nsummary: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
