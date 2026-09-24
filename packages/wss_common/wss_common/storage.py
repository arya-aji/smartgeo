"""S3 / Garage object-storage access and canonical key layout.

All object keys are produced by the helpers below so the API and the workers
always agree on the layout (PRD sections 17 & 18):

    original/{uuid}.{ext}
    maps/{idsubsls}.jpg
    review/{uuid}.jpg
    preview/{idsubsls}.webp
    georeferenced/{idsubsls}.tif
"""

from __future__ import annotations

import mimetypes
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from .config import settings

PREFIX_ORIGINAL = "original"
PREFIX_MAPS = "maps"
PREFIX_REVIEW = "review"
PREFIX_PREVIEW = "preview"
PREFIX_GEOREFERENCED = "georeferenced"

_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/tiff": "tif",
    "image/tif": "tif",
}


def _build_client(endpoint_url: str):
    addressing = "path" if settings.s3_force_path_style else "virtual"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=settings.resolved_s3_access_key,
        aws_secret_access_key=settings.resolved_s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": addressing},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


@lru_cache
def get_s3_client():
    """Cached client for server-side operations (internal network endpoint)."""
    return _build_client(settings.s3_endpoint)


@lru_cache
def get_s3_presign_client():
    """Cached client used ONLY to sign URLs the browser will call.

    It points at the publicly reachable endpoint so the SigV4 signature matches
    the Host header the browser sends. Signing happens locally, so this client
    never actually connects to that address.
    """
    return _build_client(settings.s3_public_endpoint or settings.s3_endpoint)


# --------------------------------------------------------------------------- #
# Key builders
# --------------------------------------------------------------------------- #
def content_type_to_ext(content_type: str | None, filename: str | None = None) -> str:
    if content_type and content_type.lower() in _EXT_BY_CONTENT_TYPE:
        return _EXT_BY_CONTENT_TYPE[content_type.lower()]
    if filename:
        suffix = Path(filename).suffix.lstrip(".").lower()
        if suffix:
            return "jpg" if suffix == "jpeg" else suffix
    return "jpg"


def new_original_key(content_type: str | None = None, filename: str | None = None) -> str:
    ext = content_type_to_ext(content_type, filename)
    return f"{PREFIX_ORIGINAL}/{uuid.uuid4().hex}.{ext}"


def maps_key(idsubsls: str) -> str:
    return f"{PREFIX_MAPS}/{idsubsls}.jpg"


def review_key(document_id: uuid.UUID | str) -> str:
    return f"{PREFIX_REVIEW}/{document_id}.jpg"


def preview_key(idsubsls: str) -> str:
    return f"{PREFIX_PREVIEW}/{idsubsls}.webp"


def georeferenced_key(idsubsls: str) -> str:
    return f"{PREFIX_GEOREFERENCED}/{idsubsls}.tif"


# --------------------------------------------------------------------------- #
# Operations
# --------------------------------------------------------------------------- #
def presign_put(
    key: str,
    content_type: str | None = None,
    expires_in: int | None = None,
) -> str:
    """Presigned PUT URL so the browser uploads directly to Garage."""
    params: dict[str, Any] = {"Bucket": settings.s3_bucket, "Key": key}
    if content_type:
        params["ContentType"] = content_type
    return get_s3_presign_client().generate_presigned_url(
        "put_object",
        Params=params,
        ExpiresIn=expires_in or settings.s3_presign_expire,
    )


def presign_get(
    key: str,
    expires_in: int | None = None,
    disposition: str | None = None,
) -> str:
    """Presigned GET URL for previews/downloads in the UI.

    When ``disposition`` is set (e.g. ``attachment; filename="x.jpg"``) it is
    signed into the URL so Garage returns that ``Content-Disposition`` and the
    browser downloads the object instead of rendering it inline.
    """
    params: dict[str, Any] = {"Bucket": settings.s3_bucket, "Key": key}
    if disposition:
        params["ResponseContentDisposition"] = disposition
    return get_s3_presign_client().generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in or settings.s3_presign_expire,
    )


def upload_file(local_path: str | Path, key: str, content_type: str | None = None) -> str:
    extra = {"ContentType": content_type} if content_type else None
    get_s3_client().upload_file(str(local_path), settings.s3_bucket, key, ExtraArgs=extra)
    return key


def upload_bytes(data: bytes, key: str, content_type: str | None = None) -> str:
    extra = {"ContentType": content_type} if content_type else None
    get_s3_client().put_object(Bucket=settings.s3_bucket, Key=key, Body=data, **(extra or {}))
    return key


def download_file(key: str, local_path: str | Path) -> Path:
    path = Path(local_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    get_s3_client().download_file(settings.s3_bucket, key, str(path))
    return path


def delete_object(key: str) -> None:
    get_s3_client().delete_object(Bucket=settings.s3_bucket, Key=key)


def object_exists(key: str) -> bool:
    try:
        get_s3_client().head_object(Bucket=settings.s3_bucket, Key=key)
        return True
    except ClientError:
        return False


def ensure_bucket() -> None:
    """Create the configured bucket if it does not exist yet."""
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def guess_content_type(key: str) -> str:
    return mimetypes.guess_type(key)[0] or "application/octet-stream"
