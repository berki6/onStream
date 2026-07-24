"""Worker process loop."""

from __future__ import annotations

import signal

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.webhooks.delivery import process_pending_deliveries
from src.worker.handlers.transcode_handler import process_job, shutdown_event

logger = get_logger(__name__)


def signal_handler(signum, frame):
    logger.info("Worker received shutdown signal")
    shutdown_event.set()


def run_worker():
    is_development = settings.ENV == "development"
    if is_development:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    else:
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    logger.info("Video processing worker started (ABR)")
    webhook_tick = 0

    while not shutdown_event.is_set():
        try:
            job_queue.recover_jobs_to_redis()
            upload_id = job_queue.dequeue_job(timeout=1)
            if upload_id:
                process_job(upload_id)

            webhook_tick += 1
            if webhook_tick % 5 == 0:
                try:
                    process_pending_deliveries()
                except Exception as we:
                    logger.warning(f"Webhook delivery tick failed: {we}")
        except KeyboardInterrupt:
            if is_development:
                break
            continue
        except Exception as e:
            logger.error(f"Worker error: {e}")

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    run_worker()
