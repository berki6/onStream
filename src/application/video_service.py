"""Video application service (no FastAPI).

Path param ``video_id`` means the public ``upload_id`` (8-char alphanumeric).
DB column name remains ``upload_id``.
"""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional, Tuple

from sqlalchemy.orm import Session

from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db.repositories import job_repository, video_repository
from src.infrastructure.media import ffmpeg as media_ffmpeg
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.storage import get_storage
from src.infrastructure.webhooks.delivery import emit_video_event
from src.schemas.video import VideoCreate, VideoJobCreate, VideoUpdate
from src.utils.paths import ensure_dir, to_relative_path

logger = get_logger(__name__)


def _owned_video(db: Session, video_id: str, user_id: int):
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code="not_found", status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)
    return video


def list_videos(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> Tuple[list, int]:
    if skip < 0:
        raise AppError("Skip parameter must be non-negative", code="bad_request", status_code=400)
    if limit < 1 or limit > settings.MAX_LIST_LIMIT:
        raise AppError(
            f"Limit must be between 1 and {settings.MAX_LIST_LIMIT}",
            code="bad_request",
            status_code=400,
        )
    return video_repository.list_by_user(db, user_id, skip=skip, limit=limit)


def get_video(db: Session, video_id: str, user_id: int):
    return _owned_video(db, video_id, user_id)


def update_video(db: Session, video_id: str, user_id: int, body: VideoUpdate):
    video = _owned_video(db, video_id, user_id)
    if body.title is not None:
        video.title = body.title
    if body.description is not None:
        video.description = body.description
    if body.is_public is not None:
        video.is_public = body.is_public
    db.commit()
    db.refresh(video)
    return video


def delete_video(db: Session, video_id: str, user_id: int) -> None:
    video = _owned_video(db, video_id, user_id)
    storage = get_storage()
    try:
        if video.file_path and video.file_path != "temp":
            storage.delete(video.file_path)
    except Exception as e:
        logger.warning(f"Failed to remove video file {video.file_path}: {e}")

    try:
        if video.hls_path:
            hls_prefix = str(Path(video.hls_path).parent).replace("\\", "/")
            storage.delete_prefix(hls_prefix)
    except Exception as e:
        logger.warning(f"Failed to clean up HLS for video {video.id}: {e}")

    try:
        if video.thumbnail_path:
            storage.delete(video.thumbnail_path)
    except Exception as e:
        logger.warning(f"Failed to remove thumbnail {video.thumbnail_path}: {e}")

    video_repository.soft_delete(db, video_id)
    try:
        emit_video_event(db, video, "video.deleted")
    except Exception as e:
        logger.warning(f"Webhook emit failed on delete: {e}")


def create_multipart_upload(
    db: Session,
    user_id: int,
    *,
    filename: str,
    content_type: Optional[str],
    file_size: Optional[int],
    title: Optional[str],
    description: Optional[str],
    file_obj,
) -> Any:
    """Save multipart upload, create video + job, enqueue processing."""
    if not title and filename:
        filename_without_ext = os.path.splitext(filename)[0]
        title = filename_without_ext.replace("_", " ").replace("-", " ").title()
    if not title:
        title = "Untitled Video"

    if file_size is None:
        raise AppError("File size cannot be determined", code="bad_request", status_code=400)
    if file_size > settings.MAX_UPLOAD_SIZE:
        max_size_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise AppError(
            f"File too large. Maximum size is {max_size_mb}MB",
            code="too_large",
            status_code=413,
        )
    if not content_type or not content_type.startswith("video/"):
        raise AppError(
            "Invalid file type. Only video files are allowed",
            code="bad_request",
            status_code=400,
        )
    if not filename:
        raise AppError("Filename is required", code="bad_request", status_code=400)
    if title and len(title.strip()) > settings.MAX_TITLE_LENGTH:
        raise AppError(
            f"Title must be {settings.MAX_TITLE_LENGTH} characters or less",
            code="bad_request",
            status_code=400,
        )

    temp_filename = f"temp_{uuid.uuid4().hex}_{filename}"
    temp_path = settings.VIDEO_UPLOAD_DIR / temp_filename
    file_path = None
    ensure_dir(temp_path)
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)

        duration = media_ffmpeg.probe_duration(str(temp_path))
        # probe_duration returns 0.0 on failure; tests may mock None
        if duration is None or duration <= 0.0:
            temp_path.unlink(missing_ok=True)
            raise AppError(
                "Invalid or corrupt video file", code="bad_request", status_code=400
            )
        if duration < 1:
            temp_path.unlink(missing_ok=True)
            raise AppError(
                "Video is too short (minimum 1 second)",
                code="bad_request",
                status_code=400,
            )
        if duration > settings.MAX_VIDEO_DURATION_SECONDS:
            max_duration_minutes = settings.MAX_VIDEO_DURATION_SECONDS // 60
            temp_path.unlink(missing_ok=True)
            raise AppError(
                f"Video is too long (maximum {max_duration_minutes} minutes)",
                code="bad_request",
                status_code=400,
            )

        try:
            temp_video = video_repository.create(
                db,
                VideoCreate(
                    title=title,
                    description=description,
                    duration=duration,
                    file_path="temp",
                ),
                user_id,
            )
        except Exception as e:
            temp_path.unlink(missing_ok=True)
            logger.error(f"Failed to create video record: {e}")
            raise AppError(
                "Failed to create video record", code="server_error", status_code=500
            ) from e

        try:
            job_repository.create(
                db, VideoJobCreate(upload_id=temp_video.upload_id)
            )
        except Exception as e:
            db.rollback()
            temp_path.unlink(missing_ok=True)
            logger.error(f"Failed to create video job: {e}")
            raise AppError(
                "Failed to create processing job", code="server_error", status_code=500
            ) from e

        final_filename = f"{temp_video.id}_{uuid.uuid4().hex}_{filename}"
        file_path = settings.VIDEO_UPLOAD_DIR / final_filename
        try:
            temp_path.rename(file_path)
        except OSError as e:
            db.rollback()
            temp_path.unlink(missing_ok=True)
            logger.error(f"Failed to move video file: {e}")
            raise AppError(
                "Failed to save video file", code="server_error", status_code=500
            ) from e

        try:
            relative_key = to_relative_path(file_path)
            storage = get_storage()
            storage.put_file(relative_key, file_path)
            temp_video.file_path = relative_key
            db.commit()
            db.refresh(temp_video)
        except Exception as e:
            db.rollback()
            file_path.unlink(missing_ok=True)
            logger.error(f"Failed to update video record: {e}")
            raise AppError(
                "Failed to update video record", code="server_error", status_code=500
            ) from e

        try:
            job_queue.enqueue_job(temp_video.upload_id, db)
            emit_video_event(db, temp_video, "video.created")
        except Exception as e:
            logger.warning(f"Failed to queue video for processing: {e}")

        return temp_video
    except AppError:
        raise
    except Exception as e:
        logger.error(f"Video upload failed: {e}")
        for path in [temp_path, file_path]:
            if path and path.exists():
                try:
                    path.unlink()
                except OSError:
                    pass
        raise AppError("Video upload failed", code="server_error", status_code=500) from e
