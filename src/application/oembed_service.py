"""oEmbed 1.0 for public/unlisted watch pages and share URLs.

Share resolution validates the token but must not mint a stream JWT or
increment max_views — crawlers would burn the link.
"""

from __future__ import annotations

from html import escape as html_escape
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, quote, urlparse

from sqlalchemy.orm import Session

from src.application import share_link_service
from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.ids import validate_public_video_id
from src.application.visibility import allows_tokenless_playback
from src.core.config import settings
from src.infrastructure.db.repositories import video_repository


def _norm_host(netloc: str) -> str:
    host = (netloc or "").lower()
    if host.endswith(":443"):
        host = host[:-4]
    elif host.endswith(":80"):
        host = host[:-3]
    return host


def _host_allowed(url_host: str, request_host: str) -> bool:
    url_h = _norm_host(url_host).split(":")[0]
    req_h = _norm_host(request_host).split(":")[0]
    public = ""
    try:
        public = _norm_host(urlparse(settings.PUBLIC_API_BASE_URL).netloc).split(":")[0]
    except Exception:
        pass
    lab = {"testserver", "localhost", "127.0.0.1"}
    if url_h == req_h:
        return True
    if public and url_h == public:
        return True
    return url_h in lab and req_h in lab


def _clamp_size(maxwidth: Optional[int], maxheight: Optional[int]) -> tuple[int, int]:
    w = int(maxwidth or 640)
    w = max(200, min(w, 1280))
    if maxheight:
        h = max(113, min(int(maxheight), 720))
    else:
        h = int(round(w * 9 / 16))
    return w, h


def public_video_card(db: Session, upload_id: str) -> Dict[str, Any]:
    validate_public_video_id(upload_id)
    video = video_repository.get_by_upload_id(db, upload_id)
    if not video or not allows_tokenless_playback(video):
        raise AppError("Video not found", code=ErrorCode.OEMBED_NOT_FOUND)
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    media = {}
    if video.storyboard_path:
        media["storyboard_url"] = f"{base}/v1/playback/{upload_id}/storyboard.jpg"
    if video.storyboard_vtt_path:
        media["storyboard_vtt_url"] = f"{base}/v1/playback/{upload_id}/storyboard.vtt"
    if video.caption_vtt_path:
        media["captions_url"] = f"{base}/v1/playback/{upload_id}/captions.vtt"
    return {
        "upload_id": upload_id,
        "title": video.title,
        "duration": video.duration,
        "playback_url": f"{base}/v1/playback/{upload_id}/master.m3u8",
        **media,
    }


def _iframe(src: str, width: int, height: int) -> str:
    safe = html_escape(src, quote=True)
    return (
        f'<iframe src="{safe}" width="{width}" height="{height}" '
        f'allow="autoplay; fullscreen" allowfullscreen></iframe>'
    )


def resolve(
    db: Session,
    url: str,
    *,
    request_host: str,
    maxwidth: Optional[int] = None,
    maxheight: Optional[int] = None,
) -> Dict[str, Any]:
    raw = (url or "").strip()
    if not raw:
        raise AppError("url is required", code=ErrorCode.OEMBED_BAD_REQUEST)
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise AppError("Not an embeddable OnStream URL", code=ErrorCode.OEMBED_NOT_FOUND)
    if not _host_allowed(parsed.netloc, request_host):
        raise AppError("Not an embeddable OnStream URL", code=ErrorCode.OEMBED_NOT_FOUND)

    path = parsed.path.rstrip("/") + "/"
    if "/demo/watch" not in path:
        raise AppError("Not an embeddable OnStream URL", code=ErrorCode.OEMBED_NOT_FOUND)

    qs = parse_qs(parsed.query)
    width, height = _clamp_size(maxwidth, maxheight)
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    title = "OnStream"
    thumbnail = None
    duration = None
    watch_src = None

    v = (qs.get("v") or [None])[0]
    s = (qs.get("s") or [None])[0]
    t = (qs.get("t") or [None])[0]
    h = (qs.get("h") or [None])[0]

    try:
        if v:
            card = public_video_card(db, v)
            title = card["title"] or title
            duration = card.get("duration")
            thumbnail = card.get("storyboard_url")
            watch_src = f"{base}/demo/watch/?v={quote(v, safe='')}&embed=1"
        elif h:
            from src.application import highlight_service

            card = highlight_service.get_public(db, h)
            title = card.get("title") or title
            duration = None
            watch_src = f"{base}/demo/watch/?h={quote(h, safe='')}&embed=1"
        elif s and t:
            peeked = share_link_service.peek(db, s, t)
            title = peeked["title"] or title
            duration = peeked.get("duration")
            if peeked.get("tokenless") and peeked.get("has_storyboard"):
                thumbnail = (
                    f"{base}/v1/playback/{peeked['upload_id']}/storyboard.jpg"
                )
            watch_src = (
                f"{base}/demo/watch/?s={quote(s, safe='')}&t={quote(t, safe='')}"
                "&embed=1"
            )
        else:
            raise AppError(
                "Not an embeddable OnStream URL", code=ErrorCode.OEMBED_NOT_FOUND
            )
    except AppError as e:
        if e.code == ErrorCode.OEMBED_BAD_REQUEST:
            raise
        raise AppError(
            "Not an embeddable OnStream URL", code=ErrorCode.OEMBED_NOT_FOUND
        ) from e

    data: Dict[str, Any] = {
        "version": "1.0",
        "type": "video",
        "provider_name": "OnStream",
        "provider_url": base,
        "title": title,
        "width": width,
        "height": height,
        "html": _iframe(watch_src, width, height),
    }
    if duration:
        data["duration"] = float(duration)
    if thumbnail:
        data["thumbnail_url"] = thumbnail
        data["thumbnail_width"] = 160
        data["thumbnail_height"] = 90
    return data
