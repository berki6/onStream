"""MediaMTX control API client (soft-fail when unreachable)."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

# MediaMTX path source.type → control-API kick collection.
# Kick is per-connection id, not path name (no /v3/paths/kick/{name}).
_SOURCE_KICK_SEGMENT: Dict[str, str] = {
    "rtmpConn": "rtmpconns",
    "rtmpsConn": "rtmpsconns",
    "webRTCSession": "webrtcsessions",
    "whipSession": "webrtcsessions",
    "srtConn": "srtconns",
    "rtspSession": "rtspsessions",
    "rtspsSession": "rtspssessions",
}


def _base_url() -> str:
    return (settings.MEDIAMTX_API_URL or "").rstrip("/")


def _auth() -> Optional[httpx.BasicAuth]:
    user = (settings.MEDIAMTX_API_USER or "").strip()
    password = settings.MEDIAMTX_API_PASS or ""
    if user:
        return httpx.BasicAuth(user, password)
    return None


def _encode_path_name(name: str) -> str:
    """Encode path names so slashes survive /v3/paths/get/{name}."""
    return quote((name or "").strip().strip("/"), safe="")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
)
def _get(path: str) -> httpx.Response:
    url = f"{_base_url()}{path}"
    with httpx.Client(timeout=3.0, auth=_auth()) as client:
        return client.get(url)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
)
def _post(path: str) -> httpx.Response:
    url = f"{_base_url()}{path}"
    with httpx.Client(timeout=3.0, auth=_auth()) as client:
        return client.post(url)


def get_path(name: str) -> Optional[Dict[str, Any]]:
    """
    Fetch MediaMTX path state. Returns None if API unreachable or path missing.
    """
    if not _base_url():
        return None
    encoded = _encode_path_name(name)
    if not encoded:
        return None
    try:
        resp = _get(f"/v3/paths/get/{encoded}")
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            logger.warning(
                "MediaMTX get_path %s HTTP %s", name, resp.status_code
            )
            return None
        return resp.json()
    except Exception as exc:
        logger.warning("MediaMTX API unreachable (get_path %s): %s", name, exc)
        return None


def _kick_connection(segment: str, conn_id: str) -> bool:
    resp = _post(f"/v3/{segment}/kick/{conn_id}")
    if resp.status_code in (200, 204):
        return True
    logger.warning(
        "MediaMTX kick %s/%s HTTP %s", segment, conn_id, resp.status_code
    )
    return False


def kick_publisher(path_name: str) -> bool:
    """
    Kick the active publisher on a MediaMTX path.

    Resolves ``source.type`` + ``source.id`` via GET /v3/paths/get/{name}, then
    POSTs /v3/{rtmpconns|webrtcsessions|...}/kick/{id}. Soft-fails (False) when
    the API is down, the path is idle, or the source type is unknown.
    """
    if not _base_url():
        return False
    path_name = (path_name or "").strip().strip("/")
    if not path_name:
        return False
    try:
        info = get_path(path_name)
        if not info:
            logger.info("MediaMTX kick skipped — path missing: %s", path_name)
            return False

        source = info.get("source") or {}
        if not isinstance(source, dict):
            logger.info("MediaMTX kick skipped — no source on %s", path_name)
            return False

        source_type = str(source.get("type") or "").strip()
        conn_id = str(source.get("id") or "").strip()
        if not source_type or not conn_id:
            logger.info(
                "MediaMTX kick skipped — incomplete source on %s: %s",
                path_name,
                source,
            )
            return False

        segment = _SOURCE_KICK_SEGMENT.get(source_type)
        if not segment:
            logger.warning(
                "MediaMTX kick unknown source type %r on %s",
                source_type,
                path_name,
            )
            return False

        ok = _kick_connection(segment, conn_id)
        if ok:
            logger.info(
                "MediaMTX kicked %s (%s/%s)", path_name, segment, conn_id
            )
        return ok
    except Exception as exc:
        logger.warning(
            "MediaMTX API unreachable (kick %s): %s", path_name, exc
        )
        return False


def is_path_ready(name: str) -> bool:
    """True when path exists and has a ready publisher/reader."""
    info = get_path(name)
    if not info:
        return False
    if info.get("ready") is True:
        return True
    # Fallbacks across MediaMTX versions
    if info.get("readyTime") or info.get("tracks"):
        return True
    source = info.get("source") or {}
    if isinstance(source, dict) and source.get("type"):
        return True
    return False
