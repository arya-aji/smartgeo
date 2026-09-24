"""Health router."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from wss_common import storage
from wss_common.config import settings
from wss_common.db import engine
from wss_common.queue import get_redis

from app.schemas import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
def health_check() -> dict:
    db_ok = False
    redis_ok = False
    storage_ok = False

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    try:
        get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    try:
        storage.get_s3_client().head_bucket(Bucket=settings.s3_bucket)
        storage_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "db": db_ok,
        "redis": redis_ok,
        "storage": storage_ok,
    }
