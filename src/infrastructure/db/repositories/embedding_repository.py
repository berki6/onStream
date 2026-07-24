"""Video embedding repository."""

from __future__ import annotations

from typing import List, Sequence

from sqlalchemy.orm import Session

from src.infrastructure.db import models
from src.infrastructure.media.embeddings import embedding_to_json


def delete_for_video(db: Session, video_id: int) -> int:
    deleted = (
        db.query(models.VideoEmbedding)
        .filter(models.VideoEmbedding.video_id == video_id)
        .delete()
    )
    db.commit()
    return deleted


def replace_chunks(
    db: Session,
    video_id: int,
    chunks: Sequence[dict],
    vectors: Sequence[Sequence[float]],
) -> List[models.VideoEmbedding]:
    """Replace all embedding chunks for a video."""
    db.query(models.VideoEmbedding).filter(
        models.VideoEmbedding.video_id == video_id
    ).delete()
    rows: List[models.VideoEmbedding] = []
    for chunk, vector in zip(chunks, vectors):
        row = models.VideoEmbedding(
            video_id=video_id,
            chunk_index=int(chunk.get("chunk_index", len(rows))),
            start_ms=chunk.get("start_ms"),
            end_ms=chunk.get("end_ms"),
            text=chunk.get("text"),
            embedding=embedding_to_json(vector),
        )
        db.add(row)
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


def list_by_video(db: Session, video_id: int) -> List[models.VideoEmbedding]:
    return (
        db.query(models.VideoEmbedding)
        .filter(models.VideoEmbedding.video_id == video_id)
        .order_by(models.VideoEmbedding.chunk_index.asc())
        .all()
    )


def list_all_with_embeddings(db: Session, limit: int = 500) -> List[models.VideoEmbedding]:
    return (
        db.query(models.VideoEmbedding)
        .order_by(models.VideoEmbedding.video_id.asc())
        .limit(limit)
        .all()
    )
