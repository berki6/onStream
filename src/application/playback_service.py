"""Playback authorization and asset resolution (no FastAPI).

Path param ``video_id`` means the public ``upload_id`` (8-char alphanumeric).
"""

from __future__ import annotations

import re
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote

from jose import JWTError
from sqlalchemy.orm import Session

from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.core.config import settings
from src.core.security.tokens import create_stream_token, decode_token
from src.infrastructure.db import models
from src.infrastructure.db.repositories import video_repository
from src.infrastructure.storage import get_storage


def issue_token(
    db: Session,
    video_id: str,
    user_id: int,
    expires_in: Optional[int] = None,
) -> dict:
    """Issue a signed playback token. ``video_id`` is the public upload_id."""
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code="not_found", status_code=404)
    if video.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)
    if video.status != models.VideoStatus.READY:
        raise AppError(
            "Video is not ready for streaming", code="conflict", status_code=409
        )

    ttl = expires_in if expires_in is not None else settings.STREAM_TOKEN_EXPIRE_SECONDS
    token = create_stream_token(video_id, expires_delta=timedelta(seconds=ttl))
    playback_url = (
        f"{settings.PUBLIC_API_BASE_URL}/v1/playback/{video_id}/master.m3u8"
        f"?token={token}"
    )
    return {
        "token": token,
        "expires_in": ttl,
        "playback_url": playback_url,
    }


def check_origin(origin_or_referer: str) -> None:
    allowed = settings.stream_allowed_origins_list
    if not allowed:
        return
    if not any(origin_or_referer.startswith(a) for a in allowed):
        raise AppError("Origin not allowed", code="forbidden", status_code=403)


def authorize_access(
    video: models.Video,
    token: Optional[str],
    bearer: Optional[str],
    current_user,
    origin_or_referer: str = "",
) -> Optional[str]:
    """
    Authorize playback access.

    Returns stream token string to rewrite into playlists, if any.
    """
    check_origin(origin_or_referer)

    if video.is_public:
        return token

    candidate = token or bearer
    if candidate:
        try:
            payload = decode_token(candidate, expected_type="stream")
            if payload.get("sub") == video.upload_id:
                return candidate
        except JWTError:
            pass
        try:
            payload = decode_token(candidate, expected_type="access")
            if current_user and payload.get("sub") == current_user.username:
                if video.user_id == current_user.id:
                    return None
        except JWTError:
            pass

    if current_user and video.user_id == current_user.id:
        return None

    if current_user:
        raise AppError("Access denied", code="forbidden", status_code=403)

    raise AppError(
        "Stream token required for private video",
        code="unauthorized",
        status_code=401,
    )


def safe_asset_path(asset_path: str) -> str:
    if not asset_path:
        raise AppError("Invalid segment name", code="bad_request", status_code=400)
    normalized = asset_path.replace("\\", "/").lstrip("/")
    if ".." in normalized or normalized.startswith("/"):
        raise AppError("Stream segment not found", code="not_found", status_code=404)
    if not re.match(r"^[A-Za-z0-9_./\-]+$", normalized):
        raise AppError("Stream segment not found", code="not_found", status_code=404)
    return normalized


def rewrite_playlist(content: str, token: Optional[str]) -> bytes:
    if not token:
        return content.encode("utf-8")
    q = f"token={quote(token)}"
    out_lines = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            if "?" in stripped:
                out_lines.append(f"{stripped}&{q}")
            else:
                out_lines.append(f"{stripped}?{q}")
        else:
            out_lines.append(line)
    return ("\n".join(out_lines) + "\n").encode("utf-8")


def get_ready_video(db: Session, video_id: str) -> models.Video:
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code="not_found", status_code=404)
    if video.status != models.VideoStatus.READY:
        raise AppError(
            "Video is not ready for streaming", code="conflict", status_code=409
        )
    if not video.hls_path:
        raise AppError(
            "Stream playlist not available", code="not_found", status_code=404
        )
    return video


def resolve_master(video: models.Video) -> Tuple[Path, str]:
    """Return (local_path, storage_key) for the master playlist."""
    storage = get_storage()
    key = video.hls_path
    try:
        path = storage.ensure_local(key)
    except FileNotFoundError as e:
        raise AppError(
            "Stream playlist not available", code="not_found", status_code=404
        ) from e
    return path, key


def resolve_asset(video: models.Video, asset_path: str) -> Tuple[Path, str]:
    """Return (local_path, safe_relative_path) for an HLS asset under the video."""
    safe = safe_asset_path(asset_path)
    hls_root = str(Path(video.hls_path).parent).replace("\\", "/")
    key = f"{hls_root}/{safe}".replace("\\", "/")
    storage = get_storage()
    try:
        path = storage.ensure_local(key)
    except Exception as e:
        detail = (
            "Stream segment not found"
            if safe.endswith(".ts")
            else "Stream asset not found"
        )
        raise AppError(detail, code="not_found", status_code=404) from e
    return path, safe
