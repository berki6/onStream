"""Video job application service (no FastAPI).

Path param ``video_id`` means the public ``upload_id`` (8-char alphanumeric).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.infrastructure.db import models
from src.infrastructure.db.repositories import job_repository, video_repository
from src.infrastructure.queue.job_queue import job_queue


def _owned_video_and_job(db: Session, video_id: str, user_id: int):
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND, status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code=ErrorCode.VIDEO_FORBIDDEN, status_code=403)
    job = job_repository.get_for_video(db, video)
    if not job:
        raise AppError("Job not found", code=ErrorCode.JOB_NOT_FOUND, status_code=404)
    return video, job


def get_latest(db: Session, video_id: str, user_id: int):
    _, job = _owned_video_and_job(db, video_id, user_id)
    return job


def apply_action(db: Session, video_id: str, user_id: int, action: str):
    video, job = _owned_video_and_job(db, video_id, user_id)

    if action == "retry":
        if job.stage not in ("error", "cancelled", "ready"):
            raise AppError(
                "Job is still in progress", code=ErrorCode.JOB_CONFLICT, status_code=409
            )
        job.stage = models.JobStage.QUEUED.value
        job.status = "queued"
        job.progress = 0
        job.cancel_requested = False
        job.message = "Re-queued"
        video.status = models.VideoStatus.PENDING
        db.commit()
        if not job_queue.enqueue_job(video_id, db):
            raise AppError(
                "Failed to enqueue job for processing",
                code=ErrorCode.INTERNAL_QUEUE_FAILURE,
            )
        return job

    if action == "cancel":
        if job.stage in ("ready", "cancelled"):
            raise AppError(
                "Job cannot be cancelled", code=ErrorCode.JOB_CONFLICT, status_code=409
            )
        job.cancel_requested = True
        job.message = "Cancel requested"
        db.commit()
        return job

    raise AppError(f"Unknown action: {action}", code=ErrorCode.JOB_BAD_REQUEST, status_code=400)
