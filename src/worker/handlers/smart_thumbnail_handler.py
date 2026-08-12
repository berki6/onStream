"""Smart thumbnail job handler."""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from src.application.error_codes import ErrorCode
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.session import engine
from src.infrastructure.media.smart_thumbnail import generate_smart_assets
from src.infrastructure.queue.job_queue import job_queue

logger = get_logger(__name__)
Session = sessionmaker(bind=engine)


def process_smart_thumbnail(upload_id: str) -> None:
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
                job_type="smart_thumbnail",
                error_code=ErrorCode.VIDEO_NOT_FOUND,
            )
            return

        from src.infrastructure.storage import get_storage

        storage = get_storage()
        try:
            local = storage.ensure_local(video.file_path)
        except Exception as e:
            job_queue.mark_job_failed(
                upload_id,
                str(e),
                job_type="smart_thumbnail",
                error_code=ErrorCode.INTERNAL_STORAGE_FAILURE,
            )
            return

        thumb, preview = generate_smart_assets(str(local), video.id, upload_id)
        if thumb:
            video.thumbnail_path = thumb
        if preview:
            video.preview_clip_path = preview
        session.commit()
        job_queue.mark_job_completed(upload_id, job_type="smart_thumbnail")
        logger.info(f"Smart thumbnail ready for {upload_id}")
    except Exception as e:
        logger.error(f"Smart thumbnail failed for {upload_id}: {e}")
        job_queue.mark_job_failed(
            upload_id,
            str(e),
            job_type="smart_thumbnail",
            error_code=ErrorCode.JOB_FAILED,
        )
    finally:
        session.close()
