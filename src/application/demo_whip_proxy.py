"""Lab-only same-origin WHIP proxy so /demo/whip/ can POST without CORS."""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from src.core.config import settings


def _port(parsed) -> int:
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    return 8889


def whip_proxy_allowed(target: str) -> bool:
    """Allow WHIP URLs aimed at this lab's MediaMTX WebRTC listener."""
    try:
        got = urlparse(target)
    except Exception:
        return False
    if got.scheme not in ("http", "https"):
        return False
    path = (got.path or "").rstrip("/")
    if not path.endswith("/whip") and "/whip/" not in path:
        return False
    allowed = urlparse(settings.PUBLIC_WEBRTC_BASE_URL or "")
    hosts = {h for h in (allowed.hostname, "127.0.0.1", "localhost") if h}
    if got.hostname not in hosts:
        return False
    return _port(got) == _port(allowed) or _port(got) == 8889


def abs_session_url(target: str, location: str | None) -> str | None:
    if not location:
        return None
    return urljoin(target, location)
