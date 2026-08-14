"""CDN / edge cache headers for HLS playback responses."""

from __future__ import annotations

from src.core.config import settings


def cache_headers(*, live: bool, asset_name: str, ll: bool = False) -> dict:
    """
    Return Cache-Control (and related) headers for an HLS asset.

    No-ops to ``{}`` when ``PLAYBACK_CDN_HEADERS_ENABLED`` is false.

    Policy (tokenized URLs are unique per query string, so ``public`` is safe):

    | Asset | Live | VOD |
    |-------|------|-----|
    | ``.m3u8`` | ``max-age=0, s-maxage=1, must-revalidate`` | ``max-age=5, must-revalidate`` |
    | ``.ts`` | ``max-age=4`` | long ``immutable`` |
    | ``.vtt`` / thumbs | ``no-store`` | ``max-age=86400`` |

    Live playlists deliberately avoid ``no-store`` so a shared edge can hold the
    object for ~1s while browsers always revalidate — after revoke, CDN purge
    (or that 1s window) clears viewers.
    """
    if not settings.PLAYBACK_CDN_HEADERS_ENABLED:
        return {}

    name = (asset_name or "").lower().split("?")[0]
    is_playlist = name.endswith(".m3u8")
    is_segment = name.endswith(".ts") or name.endswith(".m4s")
    is_init = name.endswith(".mp4")
    is_caption = name.endswith(".vtt")
    is_image = name.endswith(".jpg") or name.endswith(".jpeg") or name.endswith(".png")

    headers: dict[str, str] = {}

    if live:
        if is_playlist:
            if ll:
                headers["Cache-Control"] = "public, max-age=0, s-maxage=0, must-revalidate"
            else:
                headers["Cache-Control"] = (
                    "public, max-age=0, s-maxage=1, must-revalidate"
                )
        elif is_segment:
            # Slightly above a typical 2s live segment so late joiners can hit edge.
            headers["Cache-Control"] = "public, max-age=4"
        elif is_init:
            headers["Cache-Control"] = "public, max-age=60"
        elif is_caption or is_image:
            headers["Cache-Control"] = "no-store"
        else:
            headers["Cache-Control"] = "no-store"
    else:
        # VOD
        if is_playlist:
            headers["Cache-Control"] = "public, max-age=5, must-revalidate"
        elif is_segment:
            headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif is_caption or is_image:
            headers["Cache-Control"] = "public, max-age=86400"
        else:
            headers["Cache-Control"] = "public, max-age=60"

    # Defense in depth for media MIME sniffing at the edge / browser.
    headers["X-Content-Type-Options"] = "nosniff"
    return headers
