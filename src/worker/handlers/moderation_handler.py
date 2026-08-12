"""Content moderation job handler."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from src.application.error_codes import ErrorCode
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.session import engine
from src.infrastructure.ai.registry import get_moderation_provider
from src.infrastructure.queue.job_queue import job_queue
from src.infrastructure.webhooks.delivery import emit_video_event
from src.utils.paths import to_absolute_path

logger = get_logger(__name__)
Session = sessionmaker(bind=engine)


def process_moderation(upload_id: str) -> None:
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
                job_type="moderation",
                error_code=ErrorCode.VIDEO_NOT_FOUND,
            )
            return

        text = ""
        if video.transcript_path:
            try:
                raw = Path(to_absolute_path(video.transcript_path)).read_text(
                    encoding="utf-8"
                )
                data = json.loads(raw)
                text = " ".join(
                    str(s.get("text", "")) for s in (data.get("segments") or [])
                )
            except Exception as exc:
                logger.warning(
                    "moderation transcript parse failed for %s: %s",
                    upload_id,
                    exc,
                )
        if not text:
            text = f"{video.title or ''} {video.description or ''}"

        video_path = None
        try:
            from src.infrastructure.storage import get_storage

            video_path = str(get_storage().ensure_local(video.file_path))
        except Exception as e:
            logger.warning(f"Frame scoring path resolve skipped for {upload_id}: {e}")

        result = get_moderation_provider().score(
            transcript_text=text, video_path=video_path
        )
        video.moderation_score = result["score"]
        video.moderation_labels = json.dumps(result["labels"])

        threshold = settings.AI_MODERATION_THRESHOLD
        if result["score"] >= threshold:
            video.status = models.VideoStatus.QUARANTINED
            video.is_public = False
            video.quarantined_at = datetime.now(timezone.utc)
            session.commit()
            emit_video_event(
                session,
                video,
                "video.quarantined",
                {
                    "score": result["score"],
                    "labels": result["labels"],
                    "threshold": threshold,
                },
            )
            logger.warning(
                f"Video {upload_id} quarantined (score={result['score']:.2f})"
            )
        else:
            session.commit()

        job_queue.mark_job_completed(upload_id, job_type="moderation")
    except Exception as e:
        logger.error(f"Moderation failed for {upload_id}: {e}")
        job_queue.mark_job_failed(
            upload_id,
            str(e),
            job_type="moderation",
            error_code=ErrorCode.JOB_FAILED,
        )
    finally:
        session.close()
