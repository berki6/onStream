"""Live stream application service (OBS/VLC via MediaMTX)."""

from __future__ import annotations

import hashlib
import secrets
import string
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple

from jose import JWTError
from sqlalchemy.orm import Session

from src.application.errors import AppError
from src.application import playback_service
from src.core.config import settings
from src.core.logger import bind_context, get_logger
from src.core.security.tokens import create_stream_token, decode_token
from src.infrastructure.db import models
from src.infrastructure.db.repositories import live_stream_repository
from src.infrastructure.media import live_abr

logger = get_logger(__name__)

_SAFE_CHARS = "".join(
    c for c in (string.ascii_letters + string.digits) if c not in "0O1Il"
)


def _require_live_enabled() -> None:
    if not settings.LIVE_ENABLED:
        raise AppError("Live streaming is disabled", code="forbidden", status_code=403)


def validate_stream_id(stream_id: str) -> str:
    if not stream_id or len(stream_id) != 12:
        raise AppError("Invalid stream ID format", code="invalid_id", status_code=400)
    if not all(c in _SAFE_CHARS for c in stream_id):
        raise AppError("Invalid stream ID format", code="invalid_id", status_code=400)
    return stream_id


def hash_stream_key(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _generate_stream_id(db: Session) -> str:
    while True:
        candidate = "".join(secrets.choice(_SAFE_CHARS) for _ in range(12))
        if not live_stream_repository.get_by_stream_id(db, candidate):
            return candidate


def _generate_stream_key() -> str:
    return secrets.token_urlsafe(24)


def extract_stream_key_from_path(path: str) -> str:
    """Extract stream key from MediaMTX path ``live/{key}`` or ``{key}``."""
    normalized = (path or "").strip().strip("/")
    if not normalized:
        return ""
    parts = normalized.split("/")
    if len(parts) >= 2 and parts[0].lower() == "live":
        return parts[-1]
    return parts[-1]


def _rtmp_url_for_client() -> str:
    return settings.PUBLIC_RTMP_BASE_URL.rstrip("/")


def _playback_url(stream_id: str, token: Optional[str] = None) -> str:
    base = (
        f"{settings.PUBLIC_API_BASE_URL.rstrip('/')}"
        f"/v1/playback/live/{stream_id}/master.m3u8"
    )
    if token:
        return f"{base}?token={token}"
    return base


def _webrtc_base() -> str:
    return settings.PUBLIC_WEBRTC_BASE_URL.rstrip("/")


def _whip_whep_urls(stream_key: str) -> dict:
    base = _webrtc_base()
    path = f"live/{stream_key}"
    return {
        "whip_url": f"{base}/{path}/whip",
        "whep_url": f"{base}/{path}/whep",
    }


def _to_response(
    stream: models.LiveStream,
    *,
    stream_key: Optional[str] = None,
) -> dict:
    data = {
        "stream_id": stream.stream_id,
        "title": stream.title,
        "status": stream.status,
        "is_public": stream.is_public,
        "stream_key_prefix": stream.stream_key_prefix,
        "rtmp_url": _rtmp_url_for_client(),
        "playback_url": _playback_url(stream.stream_id),
        "hls_path": stream.hls_path,
        "abr_hls_path": stream.abr_hls_path,
        "started_at": stream.started_at,
        "ended_at": stream.ended_at,
        "created_at": stream.created_at,
        "webrtc_base": _webrtc_base(),
    }
    if stream_key is not None:
        data["stream_key"] = stream_key
        data.update(_whip_whep_urls(stream_key))
    return data


def create_stream(
    db: Session,
    user_id: int,
    title: str,
    is_public: bool = False,
) -> dict:
    _require_live_enabled()
    stream_id = _generate_stream_id(db)
    plaintext_key = _generate_stream_key()
    key_hash = hash_stream_key(plaintext_key)
    prefix = plaintext_key[:8]
    bind_context(stream_id=stream_id, user_id=user_id)

    stream = live_stream_repository.create(
        db,
        stream_id=stream_id,
        user_id=user_id,
        title=title,
        stream_key_hash=key_hash,
        stream_key_prefix=prefix,
        is_public=is_public,
    )
    logger.info("Created live stream")
    return _to_response(stream, stream_key=plaintext_key)


def list_streams(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    _require_live_enabled()
    rows, total = live_stream_repository.list_by_user(
        db, user_id, skip=skip, limit=limit
    )
    return [_to_response(r) for r in rows], total


def get_stream(db: Session, stream_id: str, user_id: int) -> dict:
    _require_live_enabled()
    validate_stream_id(stream_id)
    bind_context(stream_id=stream_id, user_id=user_id)
    stream = live_stream_repository.get_by_stream_id(db, stream_id)
    if not stream or stream.status == "ended":
        raise AppError("Live stream not found", code="not_found", status_code=404)
    if stream.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)
    return _to_response(stream)


def delete_stream(db: Session, stream_id: str, user_id: int) -> dict:
    _require_live_enabled()
    validate_stream_id(stream_id)
    bind_context(stream_id=stream_id, user_id=user_id)
    stream = live_stream_repository.get_by_stream_id(db, stream_id)
    if not stream or stream.status == "ended":
        raise AppError("Live stream not found", code="not_found", status_code=404)
    if stream.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)

    # Kick publisher via MediaMTX API (soft-fail), then stop ABR
    try:
        from src.infrastructure.live import mediamtx_client

        if stream.hls_path:
            mediamtx_client.kick_publisher(stream.hls_path)
        # Also try stream_id path variants
        mediamtx_client.kick_publisher(f"live/{stream.stream_id}")
    except Exception as exc:
        logger.warning("MediaMTX kick on delete failed for %s: %s", stream_id, exc)

    # CDN purge for live playback URLs
    try:
        from src.infrastructure.cdn import get_cdn_purger

        base = settings.PUBLIC_API_BASE_URL.rstrip("/")
        get_cdn_purger().purge_urls(
            [
                f"{base}/v1/playback/live/{stream_id}/master.m3u8",
            ]
        )
    except Exception as exc:
        logger.warning("CDN purge on live delete failed for %s: %s", stream_id, exc)

    live_abr.stop_abr(stream_id)
    stream = live_stream_repository.revoke(db, stream)
    logger.info("Deleted live stream")
    return _to_response(stream)


def issue_live_token(
    db: Session,
    stream_id: str,
    user_id: int,
    expires_in: Optional[int] = None,
) -> dict:
    _require_live_enabled()
    validate_stream_id(stream_id)
    stream = live_stream_repository.get_by_stream_id(db, stream_id)
    if not stream or stream.status == "ended":
        raise AppError("Live stream not found", code="not_found", status_code=404)
    if stream.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)

    ttl = expires_in if expires_in is not None else settings.STREAM_TOKEN_EXPIRE_SECONDS
    token = create_stream_token(stream_id, expires_delta=timedelta(seconds=ttl))
    return {
        "token": token,
        "expires_in": ttl,
        "playback_url": _playback_url(stream_id, token=token),
    }


def get_stream_health(db: Session, stream_id: str, user_id: int) -> dict:
    """Owner-only live health snapshot."""
    _require_live_enabled()
    validate_stream_id(stream_id)
    stream = live_stream_repository.get_by_stream_id(db, stream_id)
    if not stream or stream.status == "ended":
        raise AppError("Live stream not found", code="not_found", status_code=404)
    if stream.user_id != user_id:
        raise AppError("Access denied", code="forbidden", status_code=403)
    from src.infrastructure.live.health import get_health_snapshot

    return get_health_snapshot(db, stream)


def _check_auth_secret(provided: Optional[str]) -> None:
    expected = (settings.MEDIAMTX_AUTH_SECRET or "").strip()
    if not expected:
        return
    if not provided or provided != expected:
        raise AppError("Unauthorized", code="unauthorized", status_code=401)


def authorize_publish(
    db: Session,
    path: str,
    action: str = "publish",
    *,
    auth_secret: Optional[str] = None,
) -> models.LiveStream:
    """
    MediaMTX auth webhook handler.

    For ``publish``: validate stream key from path and mark live.
    For ``unpublish``: mark idle and stop ABR.
    For ``read`` / ``playback``: allow if a matching non-ended stream exists
    (OnStream enforces viewer tokens on its own playback routes).
    """
    from src.core import metrics as metrics_mod

    _require_live_enabled()
    _check_auth_secret(auth_secret)

    action = (action or "publish").lower()
    key = extract_stream_key_from_path(path)
    if not key:
        try:
            metrics_mod.LIVE_AUTH_TOTAL.labels(action=action, result="deny").inc()
        except Exception:
            pass
        raise AppError("Unauthorized", code="unauthorized", status_code=401)

    key_hash = hash_stream_key(key)
    stream = live_stream_repository.get_by_stream_key_hash(db, key_hash)
    if not stream or stream.status == "ended":
        try:
            metrics_mod.LIVE_AUTH_TOTAL.labels(action=action, result="deny").inc()
        except Exception:
            pass
        raise AppError("Unauthorized", code="unauthorized", status_code=401)

    if action == "publish":
        # MediaMTX layout: hlsDirectory/{path}/index.m3u8
        relative = (path or "").strip().strip("/")
        hls_path = relative or key
        abr_path = None
        if settings.LIVE_ABR_ENABLED:
            abr_path = f"{stream.stream_id}/abr"
            live_abr.start_abr(stream.stream_id, key)

        stream = live_stream_repository.set_live(
            db, stream, hls_path=hls_path, abr_hls_path=abr_path
        )
        try:
            metrics_mod.LIVE_AUTH_TOTAL.labels(action=action, result="allow").inc()
            metrics_mod.LIVE_STREAMS_ACTIVE.set(
                live_stream_repository.count_by_status(db, "live")
            )
            metrics_mod.LIVE_ABR_ACTIVE.set(
                1 if live_abr.abr_running(stream.stream_id) else 0
            )
        except Exception:
            pass
        return stream

    if action in ("unpublish", "unpublish_all"):
        live_abr.stop_abr(stream.stream_id)
        stream = live_stream_repository.set_idle(db, stream)
        try:
            metrics_mod.LIVE_AUTH_TOTAL.labels(action="unpublish", result="allow").inc()
            metrics_mod.LIVE_STREAMS_ACTIVE.set(
                live_stream_repository.count_by_status(db, "live")
            )
            metrics_mod.LIVE_ABR_ACTIVE.set(
                sum(
                    1
                    for s in live_stream_repository.list_by_status(db, "live")
                    if live_abr.abr_running(s.stream_id)
                )
            )
        except Exception:
            pass
        return stream

    # read / playback / other: allow known keys so MediaMTX remux works
    try:
        metrics_mod.LIVE_AUTH_TOTAL.labels(action=action, result="allow").inc()
    except Exception:
        pass
    return stream


def authorize_playback(
    stream: models.LiveStream,
    token: Optional[str],
    bearer: Optional[str],
    current_user,
    origin_or_referer: str = "",
) -> Optional[str]:
    """Authorize live HLS access (mirrors VOD private/public rules)."""
    playback_service.check_origin(origin_or_referer)

    if stream.status == "ended":
        raise AppError("Live stream not found", code="not_found", status_code=404)

    is_owner = current_user is not None and stream.user_id == current_user.id

    if stream.is_public and stream.status in ("live", "idle"):
        return token

    candidate = token or bearer
    if candidate:
        try:
            payload = decode_token(candidate, expected_type="stream")
            if payload.get("sub") == stream.stream_id:
                return candidate
        except JWTError:
            pass
        try:
            payload = decode_token(candidate, expected_type="access")
            if current_user and payload.get("sub") == current_user.username:
                if stream.user_id == current_user.id:
                    return None
        except JWTError:
            pass

    if is_owner:
        return None

    if current_user:
        raise AppError("Access denied", code="forbidden", status_code=403)

    raise AppError(
        "Stream token required for private live stream",
        code="unauthorized",
        status_code=401,
    )


def get_playable_stream(db: Session, stream_id: str) -> models.LiveStream:
    validate_stream_id(stream_id)
    stream = live_stream_repository.get_by_stream_id(db, stream_id)
    if not stream or stream.status == "ended":
        raise AppError("Live stream not found", code="not_found", status_code=404)
    return stream


def _live_root() -> Path:
    root = Path(settings.LIVE_HLS_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_master(stream: models.LiveStream) -> Path:
    """Resolve master/index playlist under LIVE_HLS_DIR."""
    root = _live_root()

    candidates = []
    if settings.LIVE_ABR_ENABLED and stream.abr_hls_path:
        abr_dir = root / stream.abr_hls_path
        candidates.extend([abr_dir / "master.m3u8", abr_dir / "index.m3u8"])

    if stream.hls_path:
        hls_dir = root / stream.hls_path
        candidates.extend(
            [
                hls_dir / "master.m3u8",
                hls_dir / "index.m3u8",
            ]
        )

    # Fallbacks used in tests / early publish
    candidates.extend(
        [
            root / stream.stream_id / "master.m3u8",
            root / stream.stream_id / "index.m3u8",
        ]
    )

    for path in candidates:
        if path.is_file():
            return path

    raise AppError(
        "Live playlist not available", code="not_found", status_code=404
    )


def resolve_asset(stream: models.LiveStream, asset_path: str) -> Tuple[Path, str]:
    safe = playback_service.safe_asset_path(asset_path)
    root = _live_root()

    search_dirs = []
    if settings.LIVE_ABR_ENABLED and stream.abr_hls_path:
        search_dirs.append(root / stream.abr_hls_path)
    if stream.hls_path:
        search_dirs.append(root / stream.hls_path)
    search_dirs.append(root / stream.stream_id)

    for base in search_dirs:
        candidate = base / safe
        if candidate.is_file():
            return candidate, safe

    detail = (
        "Stream segment not found"
        if safe.endswith(".ts")
        else "Stream asset not found"
    )
    raise AppError(detail, code="not_found", status_code=404)
