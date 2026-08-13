"""Worker process loop."""

from __future__ import annotations

import signal

from src.application.error_codes import ErrorCode
from src.core.config import settings
from src.core.logger import bind_context, clear_context, get_logger
from src.infrastructure.db.session import SessionLocal
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.webhooks.delivery import process_pending_deliveries
from src.worker.handlers.captions_handler import process_captions
from src.worker.handlers.chapters_handler import process_chapters
from src.worker.handlers.embeddings_handler import process_embeddings
from src.worker.handlers.moderation_handler import process_moderation
from src.worker.handlers.smart_thumbnail_handler import process_smart_thumbnail
from src.worker.handlers.storyboard_handler import process_storyboard
from src.worker.handlers.transcode_handler import process_job, shutdown_event

logger = get_logger(__name__)

_HANDLERS = {
    "transcode": process_job,
    "captions": process_captions,
    "chapters": process_chapters,
    "moderation": process_moderation,
    "embeddings": process_embeddings,
    "smart_thumbnail": process_smart_thumbnail,
    "storyboard": process_storyboard,
}


def signal_handler(signum, frame):
    logger.info("Worker received shutdown signal")
    shutdown_event.set()


def dispatch_job(job: dict) -> None:
    upload_id = job.get("upload_id")
    job_type = job.get("job_type") or "transcode"
    bind_context(upload_id=upload_id, job_type=job_type)
    try:
        handler = _HANDLERS.get(job_type)
        if not handler:
            logger.error(f"Unknown job_type '{job_type}' for {upload_id}")
            job_queue.mark_job_failed(
                upload_id or "",
                f"Unknown job_type: {job_type}",
                job_type=job_type,
                error_code=ErrorCode.JOB_BAD_REQUEST,
            )
            return
        handler(upload_id)
    finally:
        clear_context()


def _tick_live_health() -> None:
    from src.infrastructure.live.health import check_live_streams

    db = SessionLocal()
    try:
        check_live_streams(db)
    finally:
        db.close()


def _tick_qoe_canary() -> None:
    try:
        from src.infrastructure.live.qoe_canary import run_qoe_canary

        db = SessionLocal()
        try:
            run_qoe_canary(db)
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"QoE canary tick failed: {exc}")


def run_worker():
    is_development = settings.ENV == "development"
    if is_development:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    else:
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    try:
        from src.core.otel import setup_tracing

        setup_tracing(service_name="onstream-worker")
    except Exception as e:
        logger.warning(f"Worker OTel setup skipped: {e}")

    logger.info("Video processing worker started (ABR + AI)")
    webhook_tick = 0

    while not shutdown_event.is_set():
        try:
            job_queue.recover_jobs_to_redis()
            job = job_queue.dequeue_job(timeout=1)
            if job:
                dispatch_job(job)

            webhook_tick += 1
            if webhook_tick % 5 == 0:
                try:
                    process_pending_deliveries()
                except Exception as we:
                    logger.warning(f"Webhook delivery tick failed: {we}")
                try:
                    _tick_live_health()
                except Exception as he:
                    logger.warning(f"Live health tick failed: {he}")
                try:
                    _tick_qoe_canary()
                except Exception as qe:
                    logger.warning(f"QoE canary tick failed: {qe}")
        except KeyboardInterrupt:
            if is_development:
                break
            continue
        except Exception as e:
            logger.error(f"Worker error: {e}")

    logger.info("Worker shutdown complete")


if __name__ == "__main__":
    run_worker()
