"""CDN / edge cache headers for HLS playback responses."""

from __future__ import annotations

from src.core.config import settings


def cache_headers(*, live: bool, asset_name: str) -> dict:
    """
    Return Cache-Control (and related) headers for an HLS asset.

    No-ops to ``{}`` when ``PLAYBACK_CDN_HEADERS_ENABLED`` is false.
    """
    if not settings.PLAYBACK_CDN_HEADERS_ENABLED:
        return {}

    name = (asset_name or "").lower().split("?")[0]
    is_playlist = name.endswith(".m3u8")
    is_segment = name.endswith(".ts")

    if live:
        if is_playlist:
            return {
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            }
        if is_segment:
            return {"Cache-Control": "public, max-age=2"}
        return {"Cache-Control": "no-store"}

    # VOD
    if is_playlist:
        return {"Cache-Control": "public, max-age=3"}
    if is_segment:
        return {"Cache-Control": "public, max-age=31536000, immutable"}
    if name.endswith(".vtt") or name.endswith(".jpg") or name.endswith(".jpeg"):
        return {"Cache-Control": "public, max-age=86400"}
    return {"Cache-Control": "public, max-age=60"}
