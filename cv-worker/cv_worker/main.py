"""CV worker entrypoint: dequeue jobs from Redis and run the processing pipeline."""

from __future__ import annotations

import logging
import signal
import sys
import time
from typing import Any

from wss_common import settings
from wss_common.enums import JobType
from wss_common.queue import ack, dequeue_blocking, nack, requeue_stale

from cv_worker.processor import process_document

logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
_shutdown_requested = False


def _handle_signal(signum: int, _frame: Any) -> None:
    global _shutdown_requested
    logger.info("Received signal %d, shutting down gracefully...", signum)
    _shutdown_requested = True


def _setup_logging() -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def run_worker() -> None:
    """Main worker loop."""
    global _shutdown_requested
    _setup_logging()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    logger.info("CV worker starting (engine=%s)", settings.ocr_engine)

    # Requeue stale jobs from previous crashes
    try:
        count = requeue_stale(JobType.CV_PROCESS)
        if count:
            logger.info("Requeued %d stale CV jobs", count)
    except Exception as exc:
        logger.warning("Failed to requeue stale jobs: %s", exc)

    while not _shutdown_requested:
        try:
            item = dequeue_blocking(JobType.CV_PROCESS, timeout=5)
            if item is None:
                continue
            raw, message = item
            map_document_id = message.get("map_document_id")
            job_id = message.get("job_id")
            attempt = message.get("attempt", 1)

            logger.info("Processing job %s document %s attempt %d", job_id, map_document_id, attempt)
            result = process_document(map_document_id, job_id=job_id)

            if result.get("decision") in ("COMPLETED", "NEEDS_REVIEW"):
                ack(JobType.CV_PROCESS, raw)
                logger.info("Job %s acked (%s)", job_id, result["decision"])
            else:
                should_requeue = attempt < settings.job_max_attempts
                nack(JobType.CV_PROCESS, raw, requeue=should_requeue)
                logger.warning(
                    "Job %s nacked (requeue=%s) reason=%s",
                    job_id,
                    should_requeue,
                    result.get("reason"),
                )
        except Exception as exc:
            logger.exception("Unexpected error in worker loop: %s", exc)
            time.sleep(1)

    logger.info("CV worker stopped gracefully")


if __name__ == "__main__":
    run_worker()
