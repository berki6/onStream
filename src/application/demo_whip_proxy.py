"""Lab-only same-origin WHIP proxy so /demo/whip/ can POST without CORS.

Used when the demo page is http://127.0.0.1:8000 (PC). Phone HTTPS posts
WHIP SDP same-origin to Caddy `/live/*` and never hits this proxy — httpx
would not trust mkcert.
"""

from __future__ import annotations

from urllib.parse import urljoin, urlparse

from src.core.config import settings


def _port(parsed) -> int:
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == "https":
        return 443
    if parsed.scheme == "http":
        return 80
    return 8889


def _allowed_hosts() -> set[str]:
    hosts = {"127.0.0.1", "localhost"}
    for raw in (
        settings.PUBLIC_WEBRTC_BASE_URL,
        settings.PUBLIC_HTTPS_BASE_URL,
        settings.PUBLIC_API_BASE_URL,
    ):
        host = urlparse(raw or "").hostname
        if host:
            hosts.add(host)
    return hosts


def _allowed_ports() -> set[int]:
    ports = {80, 443, 8889}
    for raw in (settings.PUBLIC_WEBRTC_BASE_URL, settings.PUBLIC_HTTPS_BASE_URL):
        parsed = urlparse(raw or "")
        if parsed.scheme in ("http", "https"):
            ports.add(_port(parsed))
    return ports


def whip_proxy_allowed(target: str) -> bool:
    """Allow WHIP URLs aimed at this lab's MediaMTX / Caddy edge."""
    try:
        got = urlparse(target)
    except Exception:
        return False
    if got.scheme not in ("http", "https"):
        return False
    path = (got.path or "").rstrip("/")
    if not path.endswith("/whip") and "/whip/" not in path:
        return False
    if got.hostname not in _allowed_hosts():
        return False
    return _port(got) in _allowed_ports()


def abs_session_url(target: str, location: str | None) -> str | None:
    if not location:
        return None
    return urljoin(target, location)
