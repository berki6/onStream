"""Keyword and semantic search over videos."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.infrastructure.db import models
from src.infrastructure.db.repositories import video_repository
from src.infrastructure.media.embeddings import (
    cosine_similarity,
    embed_texts,
    embedding_from_json,
)


def search(
    db: Session,
    user_id: int,
    q: str,
    mode: str = "keyword",
    limit: int = 20,
) -> Dict[str, Any]:
    q = (q or "").strip()
    if not q:
        raise AppError("Query 'q' is required", code=ErrorCode.SEARCH_BAD_REQUEST, status_code=400)
    limit = max(1, min(int(limit or 20), 100))
    mode = (mode or "keyword").lower()

    if mode == "keyword":
        videos = video_repository.search_keyword(db, user_id, q, limit=limit)
        results = [
            {
                "upload_id": v.upload_id,
                "title": v.title,
                "description": v.description,
                "score": 1.0,
                "status": v.status.value if hasattr(v.status, "value") else str(v.status),
            }
            for v in videos
        ]
        return {"mode": "keyword", "q": q, "results": results}

    if mode == "semantic":
        query_vec = embed_texts([q])[0]
        rows = (
            db.query(models.VideoEmbedding, models.Video)
            .join(models.Video, models.Video.id == models.VideoEmbedding.video_id)
            .filter(models.Video.user_id == user_id)
            .filter(models.Video.status != models.VideoStatus.DELETED)
            .all()
        )
        best: Dict[int, Dict[str, Any]] = {}
        for emb, video in rows:
            vec = embedding_from_json(emb.embedding)
            score = cosine_similarity(query_vec, vec)
            prev = best.get(video.id)
            if prev is None or score > prev["score"]:
                best[video.id] = {
                    "upload_id": video.upload_id,
                    "title": video.title,
                    "description": video.description,
                    "score": score,
                    "status": (
                        video.status.value
                        if hasattr(video.status, "value")
                        else str(video.status)
                    ),
                }
        ranked = sorted(best.values(), key=lambda r: r["score"], reverse=True)[:limit]
        return {"mode": "semantic", "q": q, "results": ranked}

    raise AppError(
        "mode must be 'keyword' or 'semantic'",
        code=ErrorCode.SEARCH_BAD_REQUEST,
        status_code=400,
    )
