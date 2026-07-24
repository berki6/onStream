"""Embedding generation job handler."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from src.application.error_codes import ErrorCode
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.repositories import embedding_repository
from src.infrastructure.db.session import engine
from src.infrastructure.media.embeddings import chunk_transcript, embed_texts
from src.infrastructure.queue.job_queue import job_queue
from src.utils.paths import to_absolute_path

logger = get_logger(__name__)
Session = sessionmaker(bind=engine)


def process_embeddings(upload_id: str) -> None:
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
                job_type="embeddings",
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
                logger.warning(f"Transcript load failed for {upload_id}: {e}")

        if not segments:
            # Fallback: embed title/description as a single chunk
            text = f"{video.title or ''} {video.description or ''}".strip()
            segments = [{"start": 0, "end": video.duration or 0, "text": text or "video"}]

        chunks = chunk_transcript(segments)
        texts = [c["text"] for c in chunks]
        vectors = embed_texts(texts, provider=settings.AI_EMBEDDINGS_PROVIDER)
        embedding_repository.replace_chunks(session, video.id, chunks, vectors)
        job_queue.mark_job_completed(upload_id, job_type="embeddings")
        logger.info(f"Embeddings ready for {upload_id} ({len(chunks)} chunks)")
    except Exception as e:
        logger.error(f"Embeddings failed for {upload_id}: {e}")
        job_queue.mark_job_failed(
            upload_id,
            str(e),
            job_type="embeddings",
            error_code=ErrorCode.JOB_FAILED,
        )
    finally:
        session.close()
