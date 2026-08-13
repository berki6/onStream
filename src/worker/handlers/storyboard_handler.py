"""Storyboard + poster thumbnail for videos that skip the ABR transcode path.

Live → VOD promote inserts a READY row immediately. Previews are additive and
must not block revoke or playback.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import sessionmaker

from src.application.error_codes import ErrorCode
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.session import engine
from src.infrastructure.media.storyboard import generate_storyboard
from src.infrastructure.media.thumbnail import generate_thumbnail
from src.infrastructure.queue.job_queue import job_queue
from src.utils.paths import to_absolute_path

logger = get_logger(__name__)
Session = sessionmaker(bind=engine)

JOB_TYPE = "storyboard"


def process_storyboard(upload_id: str) -> None:
    session = Session()
    try:
        video = (
            session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        if not video:
            job_queue.mark_job_failed(
                upload_id,
                "Video not found",
                job_type=JOB_TYPE,
                error_code=ErrorCode.VIDEO_NOT_FOUND,
            )
            return
        if video.storyboard_path and video.thumbnail_path:
            job_queue.mark_job_completed(upload_id, job_type=JOB_TYPE)
            return

        from src.infrastructure.storage import get_storage

        storage = get_storage()
        try:
            local = storage.ensure_local(video.file_path)
        except Exception as e:
            job_queue.mark_job_failed(
                upload_id,
                str(e),
                job_type=JOB_TYPE,
                error_code=ErrorCode.INTERNAL_STORAGE_FAILURE,
            )
            return

        duration = video.duration
        if not duration or duration <= 0:
            from src.infrastructure.media import live_record

            duration = live_record.playlist_media_duration(local)

        dest = Path(settings.VIDEO_HLS_DIR) / video.upload_id
        dest.mkdir(parents=True, exist_ok=True)

        sprite, vtt = (None, None)
        if duration and duration > 0 and not video.storyboard_path:
            sprite, vtt = generate_storyboard(str(local), dest, float(duration))
        thumb = None
        if not video.thumbnail_path:
            thumb = generate_thumbnail(str(local), video.id)

        if sprite:
            video.storyboard_path = sprite
        if vtt:
            video.storyboard_vtt_path = vtt
        if thumb:
            video.thumbnail_path = thumb
        if duration and (not video.duration or video.duration <= 0):
            video.duration = duration
        session.commit()

        try:
            if sprite:
                storage.put_file(sprite, to_absolute_path(sprite))
            if vtt:
                storage.put_file(vtt, to_absolute_path(vtt))
            if thumb:
                storage.put_file(thumb, to_absolute_path(thumb))
        except Exception as storage_err:
            logger.warning(
                "Storyboard storage sync warning for %s: %s", upload_id, storage_err
            )

        job_queue.mark_job_completed(upload_id, job_type=JOB_TYPE)
        logger.info("Storyboard ready for %s", upload_id)
    except Exception as e:
        logger.error("Storyboard job failed for %s: %s", upload_id, e)
        job_queue.mark_job_failed(
            upload_id,
            str(e),
            job_type=JOB_TYPE,
            error_code=ErrorCode.JOB_FAILED,
        )
    finally:
        session.close()
