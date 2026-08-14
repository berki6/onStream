"""Named clip windows on a READY video. Playback is the same HLS + JWT clip."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.application.playback_service import issue_token, normalize_clip_window
from src.application.visibility import allows_tokenless_playback
from src.core.config import settings
from src.core.security.tokens import create_stream_token
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus
from src.infrastructure.db.repositories import highlight_repository, video_repository
from src.utils.upload_id import generate_upload_id

MAX_HIGHLIGHTS_PER_VIDEO = 50
_WINDOW_EPS = 0.05


def _unique_public_id(db: Session) -> str:
    for _ in range(20):
        pid = generate_upload_id(8)
        if not highlight_repository.get_by_public_id(db, pid):
            return pid
    raise AppError("Could not allocate highlight id", code=ErrorCode.INTERNAL_SERVER_ERROR)


def _owned_video(db: Session, user_id: int, upload_id: str) -> models.Video:
    validate_public_video_id(upload_id)
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or video.user_id != user_id:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
    return video


def _visible_video(db: Session, upload_id: str, user_id: Optional[int]) -> models.Video:
    validate_public_video_id(upload_id)
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
    if user_id is not None and video.user_id == user_id:
        return video
    if allows_tokenless_playback(video):
        return video
    raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)


def _serialize(
    row: models.VideoHighlight, video: models.Video, *, include_playback: bool
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "public_id": row.public_id,
        "video_id": video.upload_id,
        "title": row.title,
        "start": row.start_seconds,
        "end": row.end_seconds,
        "created_at": row.created_at,
    }
    if include_playback and allows_tokenless_playback(video):
        base = settings.PUBLIC_API_BASE_URL.rstrip("/")
        data["watch_url"] = f"{base}/demo/watch/?h={row.public_id}"
    return data


def create(
    db: Session,
    user_id: int,
    upload_id: str,
    *,
    start: float,
    end: Optional[float],
    title: Optional[str] = None,
) -> Dict[str, Any]:
    video = _owned_video(db, user_id, upload_id)
    if video.status != VideoStatus.READY:
        raise AppError(
            "Only READY videos can have highlights",
            code=ErrorCode.HIGHLIGHT_BAD_REQUEST,
        )
    start_n, end_n = normalize_clip_window(start, end, duration=video.duration)
    if start_n is None or end_n is None:
        raise AppError(
            "highlights need both start and end",
            code=ErrorCode.HIGHLIGHT_BAD_REQUEST,
        )
    if highlight_repository.count_for_video(db, video.id) >= MAX_HIGHLIGHTS_PER_VIDEO:
        raise AppError(
            f"At most {MAX_HIGHLIGHTS_PER_VIDEO} highlights per video",
            code=ErrorCode.HIGHLIGHT_BAD_REQUEST,
        )
    label = (title or "").strip() or f"{int(start_n)}s–{int(end_n)}s"
    row = models.VideoHighlight(
        public_id=_unique_public_id(db),
        video_id=video.id,
        created_by_user_id=user_id,
        title=label[:120],
        start_seconds=start_n,
        end_seconds=end_n,
    )
    try:
        saved = highlight_repository.create(db, row)
    except IntegrityError:
        raise AppError(
            "A highlight already exists for that window",
            code=ErrorCode.HIGHLIGHT_BAD_REQUEST,
        )
    return _serialize(saved, video, include_playback=True)


def list_for_video(
    db: Session, upload_id: str, user_id: Optional[int]
) -> List[Dict[str, Any]]:
    video = _visible_video(db, upload_id, user_id)
    if video.status != VideoStatus.READY:
        return []
    rows = highlight_repository.list_for_video(db, video.id)
    public = allows_tokenless_playback(video)
    owner = user_id is not None and video.user_id == user_id
    return [_serialize(r, video, include_playback=public or owner) for r in rows]


def get_public(db: Session, public_id: str) -> Dict[str, Any]:
    row = highlight_repository.get_by_public_id(db, public_id)
    if not row:
        raise AppError("Highlight not found", code=ErrorCode.HIGHLIGHT_NOT_FOUND)
    video = video_repository.get_by_id(db, row.video_id)
    if not video or not allows_tokenless_playback(video):
        raise AppError("Highlight not found", code=ErrorCode.HIGHLIGHT_NOT_FOUND)
    data = _serialize(row, video, include_playback=True)
    data["title"] = row.title or video.title
    data["video_title"] = video.title
    data["duration"] = video.duration
    ttl = settings.STREAM_TOKEN_EXPIRE_SECONDS
    token = create_stream_token(
        video.upload_id,
        expires_delta=timedelta(seconds=ttl),
        clip_start=row.start_seconds,
        clip_end=row.end_seconds,
    )
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    data["playback_url"] = (
        f"{base}/v1/playback/{video.upload_id}/master.m3u8?token={token}"
    )
    return data


def get_owned(
    db: Session, user_id: int, upload_id: str, public_id: str
) -> tuple[models.VideoHighlight, models.Video]:
    video = _owned_video(db, user_id, upload_id)
    row = highlight_repository.get_by_public_id(db, public_id)
    if not row or row.video_id != video.id:
        raise AppError("Highlight not found", code=ErrorCode.HIGHLIGHT_NOT_FOUND)
    return row, video


def delete(db: Session, user_id: int, upload_id: str, public_id: str) -> Dict[str, Any]:
    row, _video = get_owned(db, user_id, upload_id, public_id)
    highlight_repository.delete(db, row)
    return {"deleted": True, "public_id": public_id}


def issue_playback(
    db: Session, user_id: int, upload_id: str, public_id: str
) -> Dict[str, Any]:
    row, video = get_owned(db, user_id, upload_id, public_id)
    data = issue_token(
        db,
        video.upload_id,
        user_id,
        clip_start=row.start_seconds,
        clip_end=row.end_seconds,
    )
    data["highlight_id"] = row.public_id
    data["title"] = row.title
    return data


def import_chapters(db: Session, user_id: int, upload_id: str) -> List[Dict[str, Any]]:
    video = _owned_video(db, user_id, upload_id)
    if video.status != VideoStatus.READY:
        raise AppError(
            "Only READY videos can have highlights",
            code=ErrorCode.HIGHLIGHT_BAD_REQUEST,
        )
    chapters: List[Any] = []
    if video.chapters_json:
        try:
            parsed = json.loads(video.chapters_json)
            if isinstance(parsed, list):
                chapters = parsed
        except (json.JSONDecodeError, TypeError):
            chapters = []
    if not chapters:
        return []
    existing = highlight_repository.list_for_video(db, video.id)
    created: List[Dict[str, Any]] = []
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        try:
            start = float(ch.get("start"))
        except (TypeError, ValueError):
            continue
        end_raw = ch.get("end")
        end = float(end_raw) if end_raw is not None else None
        try:
            start_n, end_n = normalize_clip_window(
                start, end, duration=video.duration
            )
        except AppError:
            continue
        if start_n is None or end_n is None:
            continue
        if any(
            abs(r.start_seconds - start_n) < _WINDOW_EPS
            and abs(r.end_seconds - end_n) < _WINDOW_EPS
            for r in existing
        ):
            continue
        if highlight_repository.count_for_video(db, video.id) >= MAX_HIGHLIGHTS_PER_VIDEO:
            break
        title = str(ch.get("title") or "").strip() or f"{int(start_n)}s–{int(end_n)}s"
        row = models.VideoHighlight(
            public_id=_unique_public_id(db),
            video_id=video.id,
            created_by_user_id=user_id,
            title=title[:120],
            start_seconds=start_n,
            end_seconds=end_n,
        )
        try:
            saved = highlight_repository.create(db, row)
        except IntegrityError:
            continue
        existing.append(saved)
        created.append(_serialize(saved, video, include_playback=True))
    return created
