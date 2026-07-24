"""MediaMTX control API client (soft-fail when unreachable)."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)


def _base_url() -> str:
    return (settings.MEDIAMTX_API_URL or "").rstrip("/")


def _auth() -> Optional[httpx.BasicAuth]:
    user = (settings.MEDIAMTX_API_USER or "").strip()
    password = settings.MEDIAMTX_API_PASS or ""
    if user:
        return httpx.BasicAuth(user, password)
    return None


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
    name = (name or "").strip().strip("/")
    try:
        resp = _get(f"/v3/paths/get/{name}")
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


def kick_publisher(path_name: str) -> bool:
    """
    Kick the publisher on a path. Soft-fails (returns False) if API unreachable.
    """
    if not _base_url():
        return False
    path_name = (path_name or "").strip().strip("/")
    try:
        # MediaMTX v1/v3: POST /v3/paths/kick/{name}
        resp = _post(f"/v3/paths/kick/{path_name}")
        if resp.status_code in (200, 204):
            return True
        # Older variants
        if resp.status_code == 404:
            resp = _post(f"/v3/httppaths/kick/{path_name}")
            return resp.status_code in (200, 204)
        logger.warning(
            "MediaMTX kick_publisher %s HTTP %s", path_name, resp.status_code
        )
        return False
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
