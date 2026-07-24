"""Thin caption / chapters getters."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.infrastructure.db.repositories import video_repository


def get_chapters(db: Session, video_id: str, user_id: int) -> List[Dict[str, Any]]:
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code="not_found", status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)
    if not video.chapters_json:
        return []
    try:
        data = json.loads(video.chapters_json)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def get_caption_meta(db: Session, video_id: str, user_id: int) -> Dict[str, Optional[str]]:
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code="not_found", status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)
    return {
        "caption_vtt_path": video.caption_vtt_path,
        "transcript_path": video.transcript_path,
        "detected_language": video.detected_language,
    }
