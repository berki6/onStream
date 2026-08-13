"""Share link create / revoke / exchange."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.application.media_urls import playback_media_urls
from src.application.playback_service import normalize_clip_window
from src.core.config import settings
from src.core.security.tokens import create_stream_token
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus
from src.infrastructure.db.repositories import engagement_repository, video_repository
from src.utils.upload_id import generate_upload_id


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _unique_public_id(db: Session) -> str:
    for _ in range(20):
        pid = generate_upload_id(12)
        if not engagement_repository.get_share_by_public_id(db, pid):
            return pid
    raise AppError("Could not allocate share id", code=ErrorCode.INTERNAL_SERVER_ERROR)


def _is_active(link: models.ShareLink, now: datetime) -> bool:
    if link.revoked_at is not None:
        return False
    exp = link.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= now:
        return False
    if link.max_views is not None and link.view_count >= link.max_views:
        return False
    return True


def _serialize(
    link: models.ShareLink,
    upload_id: str,
    *,
    include_secrets: bool = False,
    video_title: Optional[str] = None,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    data: Dict[str, Any] = {
        "public_id": link.public_id,
        "video_id": upload_id,
        "label": link.label,
        "expires_at": link.expires_at,
        "revoked_at": link.revoked_at,
        "max_views": link.max_views,
        "view_count": int(link.view_count or 0),
        "clip_start": link.clip_start_seconds,
        "clip_end": link.clip_end_seconds,
        "created_at": link.created_at,
        "active": _is_active(link, now),
        "video_title": video_title,
    }
    return data


def create(
    db: Session,
    user_id: int,
    upload_id: str,
    expires_in_seconds: int = 86400,
    label: Optional[str] = None,
    max_views: Optional[int] = None,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> Dict[str, Any]:
    validate_public_video_id(upload_id)
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or video.user_id != user_id:
        raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
    if video.status != VideoStatus.READY:
        raise AppError(
            "Only READY videos can be shared", code=ErrorCode.SHARE_BAD_REQUEST
        )

    start, end = normalize_clip_window(
        clip_start, clip_end, duration=video.duration
    )

    expires_in_seconds = max(60, min(int(expires_in_seconds), 60 * 60 * 24 * 90))
    token = secrets.token_urlsafe(24)
    public_id = _unique_public_id(db)
    now = datetime.now(timezone.utc)
    link = models.ShareLink(
        public_id=public_id,
        token_hash=_hash_token(token),
        video_id=video.id,
        created_by_user_id=user_id,
        label=(label or "").strip() or None,
        expires_at=now + timedelta(seconds=expires_in_seconds),
        max_views=max_views,
        view_count=0,
        clip_start_seconds=start,
        clip_end_seconds=end,
    )
    engagement_repository.create_share(db, link)

    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    watch_url = f"{base}/demo/watch/?s={public_id}&t={token}"
    app_url = f"onstream://watch?s={public_id}&t={token}"
    data = _serialize(link, upload_id, video_title=video.title)
    data.update(
        {
            "token": token,
            "watch_url": watch_url,
            "share_url": watch_url,
            "app_url": app_url,
        }
    )
    return data


def list_for_video(
    db: Session, user_id: int, upload_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    if upload_id:
        validate_public_video_id(upload_id)
        video = video_repository.get_by_upload_id(db, upload_id)
        if not video or video.user_id != user_id:
            raise AppError("Video not found", code=ErrorCode.VIDEO_NOT_FOUND)
        links = engagement_repository.list_shares_for_video(db, video.id, user_id)
        return [
            _serialize(link, video.upload_id, video_title=video.title)
            for link in links
        ]

    links = engagement_repository.list_shares_for_user(db, user_id)
    out: List[Dict[str, Any]] = []
    for link in links:
        video = video_repository.get_by_id(db, link.video_id)
        if not video:
            continue
        out.append(_serialize(link, video.upload_id, video_title=video.title))
    return out


def revoke(db: Session, user_id: int, public_id: str) -> Dict[str, Any]:
    link = engagement_repository.get_share_by_public_id(db, public_id)
    if not link or link.created_by_user_id != user_id:
        raise AppError("Share link not found", code=ErrorCode.SHARE_NOT_FOUND)
    if link.revoked_at is None:
        link.revoked_at = datetime.now(timezone.utc)
        engagement_repository.save_share(db, link)
    video = video_repository.get_by_id(db, link.video_id)
    upload_id = video.upload_id if video else ""
    title = video.title if video else None
    return _serialize(link, upload_id, video_title=title)


def exchange(db: Session, public_id: str, token: str) -> Dict[str, Any]:
    link = engagement_repository.get_share_by_public_id(db, public_id)
    if not link:
        raise AppError("Share link not found", code=ErrorCode.SHARE_NOT_FOUND)

    if not hmac.compare_digest(_hash_token(token), link.token_hash):
        raise AppError("Invalid share token", code=ErrorCode.SHARE_FORBIDDEN)

    if link.revoked_at is not None:
        raise AppError("Share link has been revoked", code=ErrorCode.SHARE_REVOKED)

    now = datetime.now(timezone.utc)
    exp = link.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= now:
        raise AppError("Share link has expired", code=ErrorCode.SHARE_EXPIRED)

    video = video_repository.get_by_id(db, link.video_id)
    if not video or video.status == VideoStatus.DELETED:
        raise AppError("Video not found", code=ErrorCode.SHARE_NOT_FOUND)
    if video.status != VideoStatus.READY:
        raise AppError("Video is not ready", code=ErrorCode.PLAYBACK_NOT_READY)

    # Atomic conditional increment — closes TOCTOU on max_views under concurrency.
    bumped = engagement_repository.try_increment_share_view(db, link.id, now=now)
    if bumped is None:
        link = engagement_repository.get_share_by_public_id(db, public_id)
        if not link or link.revoked_at is not None:
            raise AppError("Share link has been revoked", code=ErrorCode.SHARE_REVOKED)
        exp2 = link.expires_at
        if exp2.tzinfo is None:
            exp2 = exp2.replace(tzinfo=timezone.utc)
        if exp2 <= now:
            raise AppError("Share link has expired", code=ErrorCode.SHARE_EXPIRED)
        if link.max_views is not None and link.view_count >= link.max_views:
            raise AppError("Share view limit reached", code=ErrorCode.SHARE_VIEW_LIMIT)
        raise AppError("Share link not found", code=ErrorCode.SHARE_NOT_FOUND)
    link = bumped

    ttl = min(settings.STREAM_TOKEN_EXPIRE_SECONDS, 3600)
    remaining = max(60, int((exp - now).total_seconds()))
    ttl = min(ttl, remaining)
    start = link.clip_start_seconds
    end = link.clip_end_seconds
    stream = create_stream_token(
        video.upload_id,
        expires_delta=timedelta(seconds=ttl),
        clip_start=start,
        clip_end=end,
    )
    playback_url = (
        f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}/v1/playback/"
        f"{video.upload_id}/master.m3u8?token={stream}"
    )
    data = {
        "token": stream,
        "expires_in": ttl,
        "playback_url": playback_url,
        "upload_id": video.upload_id,
        "title": video.title,
        "expires_at": link.expires_at,
        "clip_start": start,
        "clip_end": end,
    }
    data.update(playback_media_urls(video, token=stream))
    return data
