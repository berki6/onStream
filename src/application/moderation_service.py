"""Moderation review application service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.infrastructure.db import models
from src.infrastructure.db.repositories import video_repository


def list_quarantined(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return video_repository.list_quarantined(db, user_id, skip=skip, limit=limit)


def review(
    db: Session,
    user_id: int,
    video_id: str,
    action: str,
    make_public: Optional[bool] = None,
) -> models.Video:
    """
    Review a quarantined video.

    action=approve -> READY; optionally restore/set is_public
    action=reject  -> keep QUARANTINED (or soft-delete via is_public=False)
    """
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code="not_found", status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)
    if video.status != models.VideoStatus.QUARANTINED:
        raise AppError(
            "Video is not quarantined", code="conflict", status_code=409
        )

    action = (action or "").lower().strip()
    if action == "approve":
        video.status = models.VideoStatus.READY
        video.quarantined_at = None
        if make_public is not None:
            video.is_public = bool(make_public)
        db.commit()
        db.refresh(video)
        return video

    if action == "reject":
        video.is_public = False
        if make_public is False:
            pass
        # Keep quarantined; stamp review time via updated_at
        video.quarantined_at = video.quarantined_at or datetime.now(timezone.utc)
        db.commit()
        db.refresh(video)
        return video

    raise AppError(
        "action must be 'approve' or 'reject'",
        code="bad_request",
        status_code=400,
    )
