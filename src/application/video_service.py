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

from src.application.enqueue import mark_enqueue_failed_and_raise
from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.core.config import settings
from src.core.logger import bind_context, get_logger
from src.infrastructure.db.repositories import job_repository, video_repository
from src.infrastructure.media import ffmpeg as media_ffmpeg
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.storage import get_storage
from src.infrastructure.webhooks.delivery import emit_video_event
from src.application.visibility import apply_visibility
from src.schemas.video import VideoCreate, VideoJobCreate, VideoUpdate
from src.utils.paths import ensure_dir, to_relative_path

logger = get_logger(__name__)


def _owned_video(db: Session, video_id: str, user_id: int):
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
    if video.user_id != user_id:
        raise AppError("Access denied", code=ErrorCode.VIDEO_FORBIDDEN)
    return video


def list_videos(
    db: Session, user_id: int, skip: int = 0, limit: int = 100
) -> Tuple[list, int]:
    if skip < 0:
        raise AppError("Skip parameter must be non-negative", code=ErrorCode.VIDEO_BAD_REQUEST)
    if limit < 1 or limit > settings.MAX_LIST_LIMIT:
        raise AppError(
            f"Limit must be between 1 and {settings.MAX_LIST_LIMIT}",
            code=ErrorCode.VIDEO_BAD_REQUEST,
        )
    return video_repository.list_by_user(db, user_id, skip=skip, limit=limit)


def get_video(db: Session, video_id: str, user_id: int):
    bind_context(upload_id=video_id, user_id=user_id)
    return _owned_video(db, video_id, user_id)


def _playback_purge_urls(upload_id: str) -> list[str]:
    base = settings.public_playback_base_url
    return [
        f"{base}/v1/playback/{upload_id}/master.m3u8",
    ]


def update_video(db: Session, video_id: str, user_id: int, body: VideoUpdate):
    bind_context(upload_id=video_id, user_id=user_id)
    video = _owned_video(db, video_id, user_id)
    was_public = bool(video.is_public)
    if body.title is not None:
        video.title = body.title
    if body.description is not None:
        video.description = body.description
    if body.visibility is not None or body.is_public is not None:
        apply_visibility(
            video, visibility=body.visibility, is_public=body.is_public
        )
    became_private = was_public and not video.is_public
    db.commit()
    db.refresh(video)
    if became_private:
        try:
            from src.infrastructure.cdn import get_cdn_purger

            get_cdn_purger().purge_urls(_playback_purge_urls(video_id))
        except Exception as e:
            logger.warning(f"CDN purge on privatize failed for {video_id}: {e}")
    return video


def delete_video(db: Session, video_id: str, user_id: int) -> None:
    bind_context(upload_id=video_id, user_id=user_id)
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

    try:
        from src.infrastructure.cdn import get_cdn_purger

        get_cdn_purger().purge_urls(_playback_purge_urls(video_id))
    except Exception as e:
        logger.warning(f"CDN purge on delete failed for {video_id}: {e}")

    video_repository.soft_delete(db, video_id)
    try:
        emit_video_event(db, video, "video.deleted")
    except Exception as e:
        logger.warning(f"Webhook emit failed on delete: {e}")
    logger.info("Deleted video")


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
        raise AppError("File size cannot be determined", code=ErrorCode.VIDEO_BAD_REQUEST)
    if file_size > settings.MAX_UPLOAD_SIZE:
        max_size_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise AppError(
            f"File too large. Maximum size is {max_size_mb}MB",
            code=ErrorCode.VIDEO_TOO_LARGE,
        )
    if not content_type or not content_type.startswith("video/"):
        raise AppError(
            "Invalid file type. Only video files are allowed",
            code=ErrorCode.VIDEO_BAD_REQUEST,
        )
    if not filename:
        raise AppError("Filename is required", code=ErrorCode.VIDEO_BAD_REQUEST)
    if title and len(title.strip()) > settings.MAX_TITLE_LENGTH:
        raise AppError(
            f"Title must be {settings.MAX_TITLE_LENGTH} characters or less",
            code=ErrorCode.VIDEO_BAD_REQUEST,
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
                "Invalid or corrupt video file", code=ErrorCode.VIDEO_INVALID_FILE
            )
        if duration < 1:
            temp_path.unlink(missing_ok=True)
            raise AppError(
                "Video is too short (minimum 1 second)",
                code=ErrorCode.VIDEO_BAD_REQUEST,
            )
        if duration > settings.MAX_VIDEO_DURATION_SECONDS:
            max_duration_minutes = settings.MAX_VIDEO_DURATION_SECONDS // 60
            temp_path.unlink(missing_ok=True)
            raise AppError(
                f"Video is too long (maximum {max_duration_minutes} minutes)",
                code=ErrorCode.VIDEO_BAD_REQUEST,
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
                "Failed to create video record", code=ErrorCode.INTERNAL_SERVER_ERROR
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
                "Failed to create processing job", code=ErrorCode.INTERNAL_SERVER_ERROR
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
                "Failed to save video file", code=ErrorCode.INTERNAL_STORAGE_FAILURE
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
                "Failed to update video record", code=ErrorCode.INTERNAL_SERVER_ERROR
            ) from e

        if not job_queue.enqueue_job(temp_video.upload_id, db):
            mark_enqueue_failed_and_raise(db, temp_video.upload_id)
        emit_video_event(db, temp_video, "video.created")

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
        raise AppError("Video upload failed", code=ErrorCode.INTERNAL_SERVER_ERROR) from e
