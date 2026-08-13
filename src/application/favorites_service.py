"""Video favorites / saved list."""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.application.media_urls import video_payload
from src.infrastructure.db.repositories import engagement_repository, video_repository


def add(db: Session, user_id: int, upload_id: str) -> Dict[str, Any]:
    validate_public_video_id(upload_id)
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or video.user_id != user_id:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
    engagement_repository.add_favorite(db, user_id, video.id)
    return {"upload_id": upload_id, "favorited": True}


def remove(db: Session, user_id: int, upload_id: str) -> Dict[str, Any]:
    validate_public_video_id(upload_id)
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or video.user_id != user_id:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
    engagement_repository.remove_favorite(db, user_id, video.id)
    return {"upload_id": upload_id, "favorited": False}


def is_favorited(db: Session, user_id: int, upload_id: str) -> bool:
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or video.user_id != user_id:
        return False
    return engagement_repository.get_favorite(db, user_id, video.id) is not None


def list_saved(db: Session, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 100))
    rows = engagement_repository.list_favorites(db, user_id, limit=limit)
    out: List[Dict[str, Any]] = []
    for fav, video in rows:
        item = video_payload(video)
        item["favorited"] = True
        item["favorited_at"] = fav.created_at
        out.append(item)
    return out


def clear_saved(db: Session, user_id: int) -> Dict[str, Any]:
    deleted = engagement_repository.clear_favorites(db, user_id)
    return {"cleared": True, "deleted": deleted}
