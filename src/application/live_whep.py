"""Tokenized WHEP signaling gateway (viewer WebRTC, no stream key in the player)."""

from __future__ import annotations

import re
import secrets
from typing import Optional, Tuple
from urllib.parse import quote, urljoin, urlparse, urlunparse

import httpx

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.queue.redis_client import (
    CircuitBreakerOpenException,
    redis_client,
)

logger = get_logger(__name__)

_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_HLS_PATH_RE = re.compile(r"^live/[A-Za-z0-9_-]{8,64}$")
_TTL_DEFAULT = 3600
MAX_SDP_BYTES = 256 * 1024


def _ttl() -> int:
    return max(60, int(getattr(settings, "STREAM_TOKEN_EXPIRE_SECONDS", _TTL_DEFAULT) or _TTL_DEFAULT))


def _redis_key(stream_id: str, session_id: str) -> str:
    return f"whep:{stream_id}:{session_id}"


def _mtx_whep_url(hls_path: str) -> str:
    base = (settings.MEDIAMTX_WEBRTC_URL or "http://127.0.0.1:8889").rstrip("/")
    path = (hls_path or "").strip().strip("/")
    if not base or not _HLS_PATH_RE.match(path):
        raise AppError("Live WHEP is not available", code=ErrorCode.LIVE_NOT_FOUND)
    return f"{base}/{path}/whep"


def _sdp_payload(sdp: str) -> bytes:
    """Keep trailing newlines; pion rejects an empty or stripped offer with EOF."""
    text = sdp or ""
    if not text.lstrip().startswith("v="):
        raise AppError("SDP offer required", code=ErrorCode.PLAYBACK_BAD_REQUEST)
    raw = text.encode("utf-8")
    if len(raw) > MAX_SDP_BYTES:
        raise AppError("SDP offer too large", code=ErrorCode.PLAYBACK_BAD_REQUEST)
    if not raw.endswith(b"\n"):
        raw += b"\r\n"
    return raw


def _bind_session_url(target: str, location: Optional[str]) -> str:
    """Keep MediaMTX path/query; force host to MEDIAMTX_WEBRTC_URL (no SSRF)."""
    if not (location or "").strip():
        raise AppError("Live WHEP session missing", code=ErrorCode.LIVE_NOT_FOUND)
    base = target if target.endswith("/") else target + "/"
    joined = urljoin(base, location.strip())
    parsed = urlparse(joined)
    tgt = urlparse(target)
    path = parsed.path or ""
    parts = [p for p in path.split("/") if p]
    if (
        parsed.scheme not in ("http", "https")
        or not tgt.netloc
        or ".." in parts
        or not path.startswith("/live/")
        or "/whep" not in path
    ):
        raise AppError("Live WHEP session missing", code=ErrorCode.LIVE_NOT_FOUND)
    return urlunparse((tgt.scheme, tgt.netloc, path, "", parsed.query, ""))


def _session_location(stream_id: str, session_id: str, token: Optional[str]) -> str:
    loc = f"/v1/playback/live/{stream_id}/whep/sessions/{session_id}"
    if token:
        return f"{loc}?token={quote(token, safe='')}"
    return loc


def _store_session(stream_id: str, session_id: str, mtx_session: str) -> None:
    try:
        redis_client.setex(_redis_key(stream_id, session_id), _ttl(), mtx_session)
    except (CircuitBreakerOpenException, OSError, Exception) as exc:
        logger.warning("WHEP session store failed: %s", exc)
        raise AppError(
            "Live WHEP session store unavailable",
            code=ErrorCode.INTERNAL_QUEUE_FAILURE,
        ) from exc


def _load_session(stream_id: str, session_id: str) -> Optional[str]:
    try:
        raw = redis_client.get(_redis_key(stream_id, session_id))
    except (CircuitBreakerOpenException, OSError, Exception) as exc:
        logger.warning("WHEP session load failed: %s", exc)
        raise AppError(
            "Live WHEP session store unavailable",
            code=ErrorCode.INTERNAL_QUEUE_FAILURE,
        ) from exc
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8")
    return str(raw)


def _drop_session(stream_id: str, session_id: str) -> None:
    try:
        redis_client.delete(_redis_key(stream_id, session_id))
    except (CircuitBreakerOpenException, OSError, Exception) as exc:
        logger.warning("WHEP session delete failed: %s", exc)


def require_live_whep(stream: models.LiveStream) -> str:
    if stream.status != "live" or not (stream.hls_path or "").strip():
        raise AppError("Live WHEP is not available", code=ErrorCode.LIVE_NOT_FOUND)
    path = stream.hls_path.strip().strip("/")
    if not _HLS_PATH_RE.match(path):
        raise AppError("Live WHEP is not available", code=ErrorCode.LIVE_NOT_FOUND)
    return path


async def _mtx_delete(url: str) -> None:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            await client.delete(url)
    except httpx.HTTPError as exc:
        logger.warning("MediaMTX WHEP DELETE failed: %s", exc)


async def offer(
    stream_id: str,
    hls_path: str,
    sdp: str,
    playback_token: Optional[str],
) -> Tuple[str, str]:
    """POST SDP to MediaMTX WHEP; return (answer_sdp, api Location).

    Must not block the event loop: MediaMTX calls back ``/v1/live/mediamtx-auth``
    on the same API before answering WHEP.
    """
    body = _sdp_payload(sdp)
    target = _mtx_whep_url(hls_path)
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            res = await client.post(
                target,
                content=body,
                headers={"Content-Type": "application/sdp"},
            )
    except httpx.HTTPError as exc:
        logger.warning("MediaMTX WHEP POST failed for %s: %s", stream_id, exc)
        raise AppError("Live WHEP upstream failed", code=ErrorCode.LIVE_NOT_FOUND) from exc

    if res.status_code not in (200, 201):
        logger.warning(
            "MediaMTX WHEP POST %s HTTP %s", stream_id, res.status_code
        )
        raise AppError("Live WHEP upstream failed", code=ErrorCode.LIVE_NOT_FOUND)

    mtx_session = _bind_session_url(target, res.headers.get("Location"))
    session_id = secrets.token_urlsafe(18)
    try:
        _store_session(stream_id, session_id, mtx_session)
    except AppError:
        await _mtx_delete(mtx_session)
        raise
    return res.text, _session_location(stream_id, session_id, playback_token)


async def stop(stream_id: str, session_id: str) -> None:
    if not _SESSION_RE.match(session_id or ""):
        raise AppError("Live WHEP session not found", code=ErrorCode.LIVE_NOT_FOUND)
    mtx_session = _load_session(stream_id, session_id)
    if not mtx_session:
        raise AppError("Live WHEP session not found", code=ErrorCode.LIVE_NOT_FOUND)
    await _mtx_delete(mtx_session)
    _drop_session(stream_id, session_id)
