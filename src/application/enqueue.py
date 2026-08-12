"""Helpers when background enqueue fails after DB writes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.infrastructure.db import models


def mark_enqueue_failed_and_raise(db: Session, upload_id: str) -> None:
    """
    Persist a fail-closed state when Redis+DB queue enqueue both fail.

    Leaves the video/job rows (if present) in ERROR so operators can retry,
    then raises INTERNAL_QUEUE_FAILURE.
    """
    video = (
        db.query(models.Video).filter(models.Video.upload_id == upload_id).first()
    )
    job = (
        db.query(models.VideoJob)
        .filter(models.VideoJob.upload_id == upload_id)
        .first()
    )
    if video is not None:
        video.status = models.VideoStatus.ERROR
    if job is not None:
        job.status = "error"
        job.stage = models.JobStage.ERROR.value
        job.progress = 0
        job.message = "Failed to enqueue job for processing"
        job.error_code = ErrorCode.INTERNAL_QUEUE_FAILURE.value
        job.cancel_requested = False
    try:
        db.commit()
    except Exception:
        db.rollback()
    raise AppError(
        "Failed to enqueue job for processing",
        code=ErrorCode.INTERNAL_QUEUE_FAILURE,
    )
