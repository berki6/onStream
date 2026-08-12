"""Watch history / continue watching application service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.infrastructure.db.repositories import engagement_repository, video_repository


def _progress_payload(upload_id: str, row) -> Dict[str, Any]:
    return {
        "upload_id": upload_id,
        "position_seconds": float(row.position_seconds or 0),
        "duration_seconds": (
            float(row.duration_seconds) if row.duration_seconds is not None else None
        ),
        "completed": bool(row.completed),
        "last_watched_at": row.last_watched_at,
    }


def _continue_item(progress, video) -> Dict[str, Any]:
    dur = progress.duration_seconds or video.duration
    pos = float(progress.position_seconds or 0)
    ratio = 0.0
    if dur and dur > 0:
        ratio = min(1.0, max(0.0, pos / float(dur)))
    return {
        "upload_id": video.upload_id,
        "title": video.title,
        "thumbnail_path": video.thumbnail_path,
        "status": video.status.value if hasattr(video.status, "value") else str(video.status),
        "position_seconds": pos,
        "duration_seconds": float(dur) if dur is not None else None,
        "completed": bool(progress.completed),
        "progress_ratio": ratio,
        "last_watched_at": progress.last_watched_at,
    }


def upsert_progress(
    db: Session,
    user_id: int,
    upload_id: str,
    position_seconds: float,
    duration_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    validate_public_video_id(upload_id)
    if position_seconds < 0:
        raise AppError("position_seconds must be >= 0", code=ErrorCode.PROGRESS_INVALID)

    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or video.user_id != user_id:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)

    dur = duration_seconds if duration_seconds is not None else video.duration
    if dur is not None and dur > 0:
        position_seconds = min(position_seconds, float(dur))
    completed = bool(dur and dur > 0 and position_seconds >= 0.9 * float(dur))
    if completed and dur:
        position_seconds = float(dur)

    row = engagement_repository.upsert_progress(
        db,
        user_id=user_id,
        video_id=video.id,
        position_seconds=position_seconds,
        duration_seconds=float(dur) if dur is not None else None,
        completed=completed,
    )
    return _progress_payload(upload_id, row)


def get_progress(db: Session, user_id: int, upload_id: str) -> Dict[str, Any]:
    validate_public_video_id(upload_id)
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or video.user_id != user_id:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
    row = engagement_repository.get_progress(db, user_id, video.id)
    if not row:
        return {
            "upload_id": upload_id,
            "position_seconds": 0.0,
            "duration_seconds": video.duration,
            "completed": False,
            "last_watched_at": None,
        }
    return _progress_payload(upload_id, row)


def list_continue(db: Session, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 20), 50))
    rows = engagement_repository.list_continue(db, user_id, limit=limit)
    return [_continue_item(p, v) for p, v in rows]


def list_history(db: Session, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    limit = max(1, min(int(limit or 50), 100))
    rows = engagement_repository.list_history(db, user_id, limit=limit)
    return [_continue_item(p, v) for p, v in rows]
