"""End-to-end smoke test for the WSS Map Processing Platform.

Exercises the real flow against a running stack:
    login -> presign -> direct upload to Garage -> complete -> poll job status

Uses only the standard library, so it can run anywhere Python is available.

Usage:
    python scripts/smoke-test.py --image test-map.jpg \
        --api http://localhost:8000 --username admin --password admin123
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin123")
    parser.add_argument("--image", required=True)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--import-target", action="append", default=[], metavar="IDSUBSLS",
                        help="IDSUBSLS value(s) to import into the master list before uploading")
    parser.add_argument("--accept-review", metavar="IDSUBSLS",
                        help="If the document lands in NEEDS_REVIEW, accept it with this ID")
    args = parser.parse_args()

    base = args.api.rstrip("/")
    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"image not found: {image_path}")
    blob = image_path.read_bytes()

    print(f"[1/6] login as {args.username}")
    _, login = _request("POST", f"{base}/api/auth/login",
                        {"username": args.username, "password": args.password})
    token = login["access_token"]  # type: ignore[index]
    print(f"      ok, role={login['user']['role']}")  # type: ignore[index]

    if args.import_target:
        _, imp = _request("POST", f"{base}/api/targets/import",
                          {"idsubsls": args.import_target}, token=token)
        print(f"[1b]  imported targets: {imp}")

    print("[2/6] presign")
    _, presign = _request("POST", f"{base}/api/uploads/presign", {
        "filename": image_path.name,
        "content_type": "image/jpeg",
        "size": len(blob),
    }, token=token)
    doc_id = presign["map_document_id"]  # type: ignore[index]
    print(f"      map_document_id={doc_id}")

    print("[3/6] direct upload to Garage")
    _request("PUT", presign["upload_url"],  # type: ignore[index]
             headers=presign["headers"], raw=blob)  # type: ignore[index]
    print("      uploaded")

    print("[4/6] complete upload")
    _, completed = _request("POST", f"{base}/api/uploads/complete", {
        "map_document_id": doc_id,
        "file_size": len(blob),
    }, token=token)
    print(f"      status={completed['map_document']['processing_status']}")  # type: ignore[index]

    print(f"[5/6] polling /api/maps/{doc_id} (timeout {args.timeout}s)")
    deadline = time.time() + args.timeout
    doc = None
    while time.time() < deadline:
        _, doc = _request("GET", f"{base}/api/maps/{doc_id}", token=token)
        status = doc["processing_status"]  # type: ignore[index]
        print(f"      {status}")
        if status in TERMINAL:
            break
        time.sleep(3)

    if doc is not None and doc.get("processing_status") == "NEEDS_REVIEW" and args.accept_review:
        print(f"[5b] accepting review with idsubsls={args.accept_review}")
        _, doc = _request("POST", f"{base}/api/review/{doc_id}/accept",
                          {"idsubsls": args.accept_review}, token=token)
        print(f"      status={doc['processing_status']}")

    print("[6/6] result")
    assert doc is not None
    for key in ("processing_status", "idsubsls", "paper_confidence", "ocr_confidence",
                "ocr_raw", "quality_score", "upscaled", "upscale_factor",
                "error_message", "review_reason", "final_object_key"):
        print(f"      {key} = {doc.get(key)}")  # type: ignore[union-attr]

    status = doc["processing_status"]  # type: ignore[index]
    if status == "COMPLETED":
        print("\nSMOKE TEST PASSED (COMPLETED)")
        return 0
    if status in TERMINAL:
        print(f"\nSMOKE TEST REACHED TERMINAL STATE: {status}")
        return 0
    print("\nSMOKE TEST FAILED (timed out)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
