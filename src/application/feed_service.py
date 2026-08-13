"""Public RSS feeds for user libraries and playlists."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime
from typing import List
from urllib.parse import quote
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.application.visibility import is_rss_listed
from src.core.config import settings
from src.infrastructure.db.base import VideoStatus
from src.infrastructure.db.repositories import (
    playlist_repository,
    user_repository,
    video_repository,
)


def _rfc2822(dt: datetime | None) -> str:
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _item_xml(
    *,
    title: str,
    link: str,
    guid: str,
    pub: datetime | None,
    description: str | None = None,
    enclosure: str | None = None,
) -> str:
    parts = [
        "<item>",
        f"<title>{escape(title)}</title>",
        f"<link>{escape(link)}</link>",
        f"<guid isPermaLink=\"false\">{escape(guid)}</guid>",
        f"<pubDate>{_rfc2822(pub)}</pubDate>",
    ]
    if description:
        parts.append(f"<description>{escape(description)}</description>")
    if enclosure:
        parts.append(
            f'<enclosure url="{escape(enclosure)}" type="image/jpeg" />'
        )
    parts.append("</item>")
    return "\n".join(parts)


def _channel(
    title: str, link: str, description: str, items: List[str]
) -> str:
    body = "\n".join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n'
        "<channel>\n"
        f"<title>{escape(title)}</title>\n"
        f"<link>{escape(link)}</link>\n"
        f'<atom:link href="{escape(link)}" rel="self" type="application/rss+xml" />\n'
        f"<description>{escape(description)}</description>\n"
        f"{body}\n"
        "</channel>\n"
        "</rss>\n"
    )


def _watch_link(upload_id: str) -> str:
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    master = f"{base}/v1/playback/{upload_id}/master.m3u8"
    return f"{base}/demo/?url={quote(master, safe='')}"


def _thumb_url(path: str | None) -> str | None:
    if not path:
        return None
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    if path.startswith("http"):
        return path
    return f"{base}/{path.lstrip('/')}"


def user_videos_rss(db: Session, username: str) -> str:
    user = user_repository.get_by_username(db, username)
    if not user:
        raise AppError("User not found", code=ErrorCode.VIDEO_NOT_FOUND)
    videos, _ = video_repository.list_public_ready(db, user.id, skip=0, limit=50)
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    self_link = f"{base}/v1/feeds/{quote(username)}/videos.rss"
    items = []
    for video in videos:
        if not is_rss_listed(video):
            continue
        items.append(
            _item_xml(
                title=video.title,
                link=_watch_link(video.upload_id),
                guid=video.upload_id,
                pub=video.created_at,
                description=video.description,
                enclosure=_thumb_url(video.thumbnail_path),
            )
        )
    return _channel(
        f"{username} on OnStream",
        self_link,
        f"Public videos from {username}",
        items,
    )


def playlist_rss(db: Session, username: str, playlist_id: int) -> str:
    user = user_repository.get_by_username(db, username)
    if not user:
        raise AppError("Playlist not found", code=ErrorCode.PLAYLIST_NOT_FOUND)
    playlist = playlist_repository.get_by_id(db, playlist_id)
    if not playlist or playlist.user_id != user.id or not playlist.is_public:
        raise AppError("Playlist not found", code=ErrorCode.PLAYLIST_NOT_FOUND)
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    self_link = (
        f"{base}/v1/feeds/{quote(username)}/playlists/{playlist_id}.rss"
    )
    items = []
    for pv in playlist_repository.get_videos(db, playlist_id):
        video = video_repository.get_by_id(db, pv.video_id)
        if not video or not is_rss_listed(video):
            continue
        if video.status != VideoStatus.READY:
            continue
        items.append(
            _item_xml(
                title=video.title,
                link=_watch_link(video.upload_id),
                guid=f"{playlist_id}:{video.upload_id}",
                pub=video.created_at,
                description=video.description,
                enclosure=_thumb_url(video.thumbnail_path),
            )
        )
    return _channel(
        playlist.name,
        self_link,
        f"Playlist by {username}",
        items,
    )
