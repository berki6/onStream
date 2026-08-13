"""Keyword and semantic search over videos."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.core.config import settings
from src.infrastructure.db.repositories import embedding_repository, video_repository
from src.infrastructure.media.embeddings import (
    cosine_similarity,
    embed_texts,
    embedding_from_json,
)

SEMANTIC_CHUNK_CAP = 2000


def _video_row(video, score: float) -> Dict[str, Any]:
    return {
        "upload_id": video.upload_id,
        "title": video.title,
        "description": video.description,
        "thumbnail_path": getattr(video, "thumbnail_path", None),
        "score": float(score),
        "status": video.status.value if hasattr(video.status, "value") else str(video.status),
    }


def capabilities(db: Session, user_id: int) -> Dict[str, Any]:
    enabled = bool(settings.AI_EMBEDDINGS_ENABLED)
    provider = (settings.AI_EMBEDDINGS_PROVIDER or "mock").lower()
    indexed = embedding_repository.count_indexed_videos(db, user_id) if enabled else 0
    reason = None
    if not enabled:
        reason = "embeddings_disabled"
    elif indexed == 0:
        reason = "no_index"
    return {
        "semantic_available": enabled,
        "provider": provider,
        "indexed_videos": indexed,
        "reason": reason,
    }


def search(
    db: Session,
    user_id: int,
    q: str,
    mode: str = "keyword",
    limit: int = 20,
) -> Dict[str, Any]:
    q = (q or "").strip()
    if not q:
        raise AppError("Query 'q' is required", code=ErrorCode.SEARCH_BAD_REQUEST)
    limit = max(1, min(int(limit or 20), 100))
    mode = (mode or "keyword").lower()
    caps = capabilities(db, user_id)

    if mode == "keyword":
        ranked = video_repository.search_keyword_with_scores(
            db, user_id, q, limit=limit
        )
        results = [_video_row(v, score) for v, score in ranked]
        return {
            "mode": "keyword",
            "q": q,
            "results": results,
            **caps,
            "skipped_incompatible": 0,
        }

    if mode == "semantic":
        if not caps["semantic_available"]:
            raise AppError(
                "Semantic search is disabled on this engine",
                code=ErrorCode.SEARCH_UNAVAILABLE,
            )
        try:
            query_vec = embed_texts([q])[0]
        except Exception as e:
            raise AppError(
                f"Embeddings provider failed: {e}",
                code=ErrorCode.SEARCH_UNAVAILABLE,
            ) from e
        qdim = len(query_vec)
        rows = embedding_repository.list_for_user(
            db, user_id, limit=SEMANTIC_CHUNK_CAP
        )
        best: Dict[int, Dict[str, Any]] = {}
        skipped = 0
        for emb, video in rows:
            vec = embedding_from_json(emb.embedding)
            if not vec or len(vec) != qdim:
                skipped += 1
                continue
            score = cosine_similarity(query_vec, vec)
            prev = best.get(video.id)
            if prev is None or score > prev["score"]:
                best[video.id] = _video_row(video, score)
        ranked = sorted(best.values(), key=lambda r: r["score"], reverse=True)[:limit]
        reason = caps["reason"]
        if skipped and not ranked:
            reason = "incompatible_index"
        elif not ranked:
            reason = "no_match"
        return {
            "mode": "semantic",
            "q": q,
            "results": ranked,
            "semantic_available": True,
            "provider": caps["provider"],
            "indexed_videos": caps["indexed_videos"],
            "reason": reason,
            "skipped_incompatible": skipped,
        }

    raise AppError(
        "mode must be 'keyword' or 'semantic'",
        code=ErrorCode.SEARCH_BAD_REQUEST,
    )
