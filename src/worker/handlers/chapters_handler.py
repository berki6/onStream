"""Chapter generation job handler."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from src.application.error_codes import ErrorCode
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.session import engine
from src.infrastructure.media.chapters import chapters_from_segments
from src.infrastructure.queue.job_queue import job_queue
from src.utils.paths import to_absolute_path

logger = get_logger(__name__)
Session = sessionmaker(bind=engine)


def process_chapters(upload_id: str) -> None:
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
                job_type="chapters",
                error_code=ErrorCode.VIDEO_NOT_FOUND,
            )
            return

        segments = []
        if video.transcript_path:
            try:
                raw = Path(to_absolute_path(video.transcript_path)).read_text(
                    encoding="utf-8"
                )
                data = json.loads(raw)
                segments = data.get("segments") or []
            except Exception as e:
                logger.warning(f"Could not load transcript for {upload_id}: {e}")

        chapters = chapters_from_segments(segments)
        video.chapters_json = json.dumps(chapters)
        if chapters and not video.suggested_title:
            video.suggested_title = chapters[0].get("title", "")[:200]
        # Simple tags from chapter titles
        tags = [c.get("title", "")[:40] for c in chapters[:5] if c.get("title")]
        if tags:
            video.suggested_tags = json.dumps(tags)
        session.commit()
        job_queue.mark_job_completed(upload_id, job_type="chapters")
        logger.info(f"Chapters ready for {upload_id} ({len(chapters)} chapters)")
    except Exception as e:
        logger.error(f"Chapters failed for {upload_id}: {e}")
        job_queue.mark_job_failed(
            upload_id,
            str(e),
            job_type="chapters",
            error_code=ErrorCode.JOB_FAILED,
        )
    finally:
        session.close()
