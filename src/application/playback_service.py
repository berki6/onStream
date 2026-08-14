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

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.application.visibility import allows_tokenless_playback
from src.core.config import settings
from src.core.security.tokens import create_stream_token, decode_token
from src.infrastructure.db import models
from src.infrastructure.db.repositories import video_repository
from src.infrastructure.media.abr import inject_subtitle_track
from src.infrastructure.storage import get_storage


def _is_playable(video: models.Video) -> bool:
    return video.status in (models.VideoStatus.READY, models.VideoStatus.QUARANTINED)


def normalize_clip_window(
    clip_start: Optional[float],
    clip_end: Optional[float],
    duration: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float]]:
    start = None if clip_start is None else float(clip_start)
    end = None if clip_end is None else float(clip_end)
    if start is None and end is None:
        return None, None
    if start is not None and start < 0:
        raise AppError("clip_start must be >= 0", code=ErrorCode.PLAYBACK_BAD_REQUEST)
    if end is not None and end < 0:
        raise AppError("clip_end must be >= 0", code=ErrorCode.PLAYBACK_BAD_REQUEST)
    if start is not None and end is not None and end <= start:
        raise AppError(
            "clip_end must be greater than clip_start",
            code=ErrorCode.PLAYBACK_BAD_REQUEST,
        )
    if duration and duration > 0:
        if start is not None and start >= duration:
            raise AppError(
                "clip_start is past video duration",
                code=ErrorCode.PLAYBACK_BAD_REQUEST,
            )
        if end is not None:
            end = min(end, duration)
    return start, end


def clip_start_from_token(token: Optional[str]) -> Optional[float]:
    if not token:
        return None
    try:
        payload = decode_token(token, expected_type="stream")
        raw = payload.get("clip_start")
        if raw is None:
            return None
        return float(raw)
    except (JWTError, TypeError, ValueError):
        return None


def inject_clip_start(content: str, offset: Optional[float]) -> str:
    if offset is None or offset <= 0:
        return content
    lines = content.splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.startswith("#EXTM3U"):
            out.append(f"#EXT-X-START:TIME-OFFSET={offset:.3f}")
            inserted = True
    dumped = "\n".join(out)
    if not dumped.endswith("\n"):
        dumped += "\n"
    return dumped


def issue_token(
    db: Session,
    video_id: str,
    user_id: int,
    expires_in: Optional[int] = None,
    clip_start: Optional[float] = None,
    clip_end: Optional[float] = None,
) -> dict:
    """Issue a signed playback token. ``video_id`` is the public upload_id."""
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.PLAYBACK_NOT_FOUND)
    if video.user_id != user_id:
        raise AppError("Access denied", code=ErrorCode.PLAYBACK_FORBIDDEN)
    if not _is_playable(video):
        raise AppError(
            "Video is not ready for streaming", code=ErrorCode.PLAYBACK_NOT_READY
        )

    start, end = normalize_clip_window(
        clip_start, clip_end, duration=video.duration
    )
    ttl = expires_in if expires_in is not None else settings.STREAM_TOKEN_EXPIRE_SECONDS
    token = create_stream_token(
        video_id,
        expires_delta=timedelta(seconds=ttl),
        clip_start=start,
        clip_end=end,
    )
    playback_url = (
        f"{settings.PUBLIC_API_BASE_URL}/v1/playback/{video_id}/master.m3u8"
        f"?token={token}"
    )
    data = {
        "token": token,
        "expires_in": ttl,
        "playback_url": playback_url,
        "clip_start": start,
        "clip_end": end,
    }
    from src.application.media_urls import playback_media_urls

    data.update(playback_media_urls(video, token=token))
    return data


def check_origin(origin_or_referer: str) -> None:
    allowed = settings.stream_allowed_origins_list
    if not allowed:
        return
    if not any(origin_or_referer.startswith(a) for a in allowed):
        raise AppError("Origin not allowed", code=ErrorCode.PLAYBACK_FORBIDDEN)


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
    Quarantined videos: only the owner may play (public access denied).
    """
    check_origin(origin_or_referer)

    is_owner = current_user is not None and video.user_id == current_user.id

    if video.status == models.VideoStatus.QUARANTINED:
        if is_owner:
            return token
        # Also allow owner via access/stream token without current_user loaded
        candidate = token or bearer
        if candidate:
            try:
                payload = decode_token(candidate, expected_type="stream")
                if payload.get("sub") == video.upload_id and is_owner:
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
        if current_user:
            raise AppError("Access denied", code=ErrorCode.PLAYBACK_FORBIDDEN)
        raise AppError(
            "Stream token required for private video",
            code=ErrorCode.PLAYBACK_UNAUTHORIZED,
        )

    if allows_tokenless_playback(video):
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

    if is_owner:
        return None

    if current_user:
        raise AppError("Access denied", code=ErrorCode.PLAYBACK_FORBIDDEN)

    raise AppError(
        "Stream token required for private video",
        code=ErrorCode.PLAYBACK_UNAUTHORIZED,
    )


def safe_asset_path(asset_path: str) -> str:
    if not asset_path:
        raise AppError("Invalid segment name", code=ErrorCode.PLAYBACK_BAD_REQUEST)
    normalized = asset_path.replace("\\", "/").lstrip("/")
    if ".." in normalized or normalized.startswith("/"):
        raise AppError("Stream segment not found", code=ErrorCode.PLAYBACK_NOT_FOUND)
    if not re.match(r"^[A-Za-z0-9_./\-]+$", normalized):
        raise AppError("Stream segment not found", code=ErrorCode.PLAYBACK_NOT_FOUND)
    return normalized


def rewrite_playlist(content: str, token: Optional[str]) -> bytes:
    """Rewrite media/playlist URIs to append a stream token query param."""
    if not token:
        return content.encode("utf-8")
    q = f"token={quote(token)}"

    try:
        import m3u8

        playlist = m3u8.loads(content)
        # Media segments
        for seg in playlist.segments or []:
            uri = seg.uri or ""
            if not uri:
                continue
            seg.uri = f"{uri}&{q}" if "?" in uri else f"{uri}?{q}"
        # Variant playlists (master)
        for pl in playlist.playlists or []:
            uri = pl.uri or ""
            if not uri:
                continue
            pl.uri = f"{uri}&{q}" if "?" in uri else f"{uri}?{q}"
        # Media tags (audio/subtitles)
        for media in playlist.media or []:
            uri = getattr(media, "uri", None) or ""
            if not uri:
                continue
            media.uri = f"{uri}&{q}" if "?" in uri else f"{uri}?{q}"
        dumped = playlist.dumps()
        if not dumped.endswith("\n"):
            dumped += "\n"
        from src.application.ll_hls import append_token_to_quoted_uris

        dumped = append_token_to_quoted_uris(dumped, token)
        return dumped.encode("utf-8")
    except Exception:
        # Fallback: line-based rewrite
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
        from src.application.ll_hls import append_token_to_quoted_uris

        dumped = "\n".join(out_lines) + "\n"
        dumped = append_token_to_quoted_uris(dumped, token)
        return dumped.encode("utf-8")


def inject_live_edge_start(content: str, offset: float = -2.0) -> str:
    """Point players at the live edge (negative TIME-OFFSET = from end of playlist)."""
    if not content or "#EXT-X-START:" in content:
        return content
    if "#EXT-X-PART:" in content:
        return content
    lines = content.splitlines()
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and line.startswith("#EXTM3U"):
            out.append(f"#EXT-X-START:TIME-OFFSET={offset:.3f}")
            inserted = True
    dumped = "\n".join(out)
    if not dumped.endswith("\n"):
        dumped += "\n"
    return dumped


def prepare_master_playlist(
    video: models.Video, content: str, stream_token: Optional[str] = None
) -> str:
    """Inject subtitle track and optional clip start offset into master playlist."""
    if video.caption_vtt_path:
        content = inject_subtitle_track(content, captions_uri="captions.vtt")
    offset = clip_start_from_token(stream_token)
    return inject_clip_start(content, offset)


def get_ready_video(db: Session, video_id: str) -> models.Video:
    validate_public_video_id(video_id)
    video = video_repository.get_by_upload_id(db, video_id)
    if not video:
        raise AppError("Video not found", code=ErrorCode.PLAYBACK_NOT_FOUND)
    if not _is_playable(video):
        raise AppError(
            "Video is not ready for streaming", code=ErrorCode.PLAYBACK_NOT_READY
        )
    if not video.hls_path:
        raise AppError(
            "Stream playlist not available", code=ErrorCode.PLAYBACK_NOT_FOUND
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
            "Stream playlist not available", code=ErrorCode.PLAYBACK_NOT_FOUND
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
        raise AppError(detail, code=ErrorCode.PLAYBACK_NOT_FOUND) from e
    return path, safe
