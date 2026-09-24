"""Consumer loop for GEO_PROCESS jobs.

Run with: python -m geo_worker.main
"""

from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

# Ensure wss_common is importable when running from geo-worker/ directory
_project_root = Path(__file__).resolve().parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from wss_common.config import settings
from wss_common.enums import JobType
from wss_common.queue import dequeue_blocking, ack, nack, requeue_stale

from geo_worker.processor import process_job

logger = logging.getLogger("geo_worker")

_shutdown_requested = False


def _handle_signal(signum: int, _frame: object) -> None:
    global _shutdown_requested
    logger.info("Received signal %s, shutting down gracefully...", signum)
    _shutdown_requested = True


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def run() -> None:
    _setup_logging()
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("Geo worker starting up...")
    recovered = requeue_stale(JobType.GEO_PROCESS)
    if recovered:
        logger.info("Requeued %d stale GEO_PROCESS job(s)", recovered)

    logger.info("Waiting for GEO_PROCESS jobs...")
    while not _shutdown_requested:
        try:
            item = dequeue_blocking(JobType.GEO_PROCESS, timeout=5)
            if item is None:
                continue
            raw, message = item
        except Exception:
            logger.exception("Redis dequeue failed; will retry in 5s")
            time.sleep(5)
            continue

        try:
            process_job(message)
            ack(JobType.GEO_PROCESS, raw)
            logger.info("Job %s completed", message.get("job_id"))
        except Exception:
            logger.exception("Job %s failed", message.get("job_id"))
            attempt = message.get("attempt", 1)
            max_attempts = settings.job_max_attempts
            requeue = attempt < max_attempts
            nack(JobType.GEO_PROCESS, raw, requeue=requeue)

    logger.info("Geo worker shutdown complete.")


if __name__ == "__main__":
    run()
