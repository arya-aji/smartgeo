"""Redis-backed work queue shared by the API (producer) and workers (consumer).

Design: a reliable list-based queue using ``BRPOPLPUSH``. Items are atomically
moved from the *pending* list to a *processing* list while they are handled.
On success the worker ACKs (LREM). On crash the item stays in the processing
list and can be recovered by :func:`requeue_stale`, which is invoked by the
worker on startup.

Queue names (contract):
    wss:cv:jobs      / wss:cv:processing
    wss:geo:jobs     / wss:geo:processing
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from redis import Redis

from .config import settings
from .enums import JobType

CV_JOBS = "wss:cv:jobs"
CV_PROCESSING = "wss:cv:processing"
GEO_JOBS = "wss:geo:jobs"
GEO_PROCESSING = "wss:geo:processing"

_QUEUES: dict[JobType, tuple[str, str]] = {
    JobType.CV_PROCESS: (CV_JOBS, CV_PROCESSING),
    JobType.GEO_PROCESS: (GEO_JOBS, GEO_PROCESSING),
}


def queue_names(job_type: JobType) -> tuple[str, str]:
    return _QUEUES[job_type]


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    """Return a cached Redis client suitable for blocking queue operations.

    redis-py applies a short default socket read timeout (observed: 5s). A
    blocking ``BRPOPLPUSH`` that waits for the same duration then raises
    ``redis.exceptions.TimeoutError`` before Redis replies, which makes workers
    spin. The socket timeout must always exceed the blocking timeout, so we set
    it explicitly and let the blocking argument govern how long we wait.
    """
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=60,
        socket_connect_timeout=10,
        health_check_interval=30,
    )


def build_message(
    job_id: str,
    map_document_id: str,
    job_type: JobType,
    attempt: int,
) -> dict[str, Any]:
    """Canonical queue message contract."""
    return {
        "job_id": str(job_id),
        "map_document_id": str(map_document_id),
        "job_type": job_type.value,
        "attempt": int(attempt),
    }


def enqueue(job_type: JobType, message: dict[str, Any]) -> None:
    jobs, _ = queue_names(job_type)
    get_redis().lpush(jobs, json.dumps(message))


def dequeue_blocking(
    job_type: JobType,
    timeout: int = 5,
) -> tuple[str, dict[str, Any]] | None:
    """Blocking pop. Returns ``(raw, parsed)`` or ``None`` on timeout."""
    jobs, processing = queue_names(job_type)
    redis = get_redis()
    raw = redis.brpoplpush(jobs, processing, timeout=timeout)
    if raw is None:
        return None
    return raw, json.loads(raw)


def ack(job_type: JobType, raw: str) -> None:
    _, processing = queue_names(job_type)
    get_redis().lrem(processing, 1, raw)


def nack(job_type: JobType, raw: str, requeue: bool = True) -> None:
    """Remove from processing; optionally push back to the pending list."""
    jobs, processing = queue_names(job_type)
    redis = get_redis()
    redis.lrem(processing, 1, raw)
    if requeue:
        redis.lpush(jobs, raw)


def queue_length(job_type: JobType) -> int:
    jobs, _ = queue_names(job_type)
    return int(get_redis().llen(jobs))


def processing_length(job_type: JobType) -> int:
    _, processing = queue_names(job_type)
    return int(get_redis().llen(processing))


def peek_processing(job_type: JobType, limit: int = 100) -> list[tuple[str, dict[str, Any]]]:
    _, processing = queue_names(job_type)
    raw_items = get_redis().lrange(processing, 0, limit - 1)
    return [(raw, json.loads(raw)) for raw in raw_items]


def requeue_stale(job_type: JobType) -> int:
    """Move everything left in the processing list back to pending.

    Called once on worker startup so jobs interrupted by a crash are retried.
    """
    jobs, processing = queue_names(job_type)
    redis = get_redis()
    count = 0
    while True:
        raw = redis.rpoplpush(processing, jobs)
        if raw is None:
            break
        count += 1
    return count
