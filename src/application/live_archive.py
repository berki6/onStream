"""Promote a finished live HLS archive into a READY VOD row."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from src.application.visibility import apply_visibility
from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus
from src.infrastructure.db.repositories import live_stream_repository, video_repository
from src.infrastructure.media import live_record
from src.infrastructure.webhooks.delivery import emit_video_event
from src.utils.paths import to_relative_path
from src.utils.upload_id import generate_unique_upload_id

logger = get_logger(__name__)

_MASTER = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=2500000
index.m3u8
"""

_COPY_SUFFIXES = {".ts", ".m4s", ".m3u8"}


def is_enabled() -> bool:
    return bool(getattr(settings, "LIVE_ARCHIVE_ENABLED", True))


def find_archive_playlist(stream: models.LiveStream) -> Optional[Path]:
    """Only the dedicated EVENT archive — never the sliding live window."""
    path = live_record.archive_playlist(stream.stream_id, create=False)
    if live_record.playlist_has_segments(path):
        return path
    return None


def _write_vod_tree(src_playlist: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    src_dir = src_playlist.parent
    for child in src_dir.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() not in _COPY_SUFFIXES:
            continue
        shutil.copy2(child, dest / child.name)
    vod_index = dest / "index.m3u8"
    if src_playlist.name != "index.m3u8" or not vod_index.exists():
        shutil.copy2(src_playlist, vod_index)
    live_record.finalize_playlist(vod_index)
    master = dest / "master.m3u8"
    master.write_text(_MASTER, encoding="utf-8")
    return master


def _existing_archive_video(
    db: Session, stream: models.LiveStream
) -> Optional[models.Video]:
    upload_id = getattr(stream, "archived_upload_id", None)
    if upload_id:
        existing = video_repository.get_by_upload_id(db, upload_id)
        if existing:
            return existing
    return video_repository.get_by_live_stream_id(db, stream.stream_id)


def promote(db: Session, stream: models.LiveStream) -> Optional[models.Video]:
    """Copy archive HLS into VIDEO_HLS_DIR and insert a READY video. Soft-fail.

    Duration comes from #EXTINF (no ffprobe). Storyboard is skipped on this
    path so revoke stays a control-plane call.
    """
    if not is_enabled():
        return None
    existing = _existing_archive_video(db, stream)
    if existing:
        if not getattr(stream, "archived_upload_id", None):
            live_stream_repository.update_fields(
                db, stream, archived_upload_id=existing.upload_id
            )
        return existing
    src = find_archive_playlist(stream)
    if src is None:
        logger.info("No live archive playlist for %s", stream.stream_id)
        return None

    upload_id = generate_unique_upload_id(db)
    dest = Path(settings.VIDEO_HLS_DIR) / upload_id
    try:
        master = _write_vod_tree(src, dest)
    except OSError as exc:
        logger.warning("Live archive copy failed for %s: %s", stream.stream_id, exc)
        return None

    duration = live_record.playlist_media_duration(dest / "index.m3u8")
    vis = "public" if stream.is_public else "private"
    video = models.Video(
        upload_id=upload_id,
        user_id=stream.user_id,
        title=stream.title,
        description=f"Archived from live {stream.stream_id}",
        duration=duration,
        file_path=to_relative_path(dest / "index.m3u8"),
        hls_path=to_relative_path(master),
        status=VideoStatus.READY,
        source="live",
        live_stream_id=stream.stream_id,
    )
    apply_visibility(video, visibility=vis)
    db.add(video)
    stream.archived_upload_id = video.upload_id
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("Live archive persist failed for %s: %s", stream.stream_id, exc)
        return None
    db.refresh(video)
    db.refresh(stream)
    try:
        emit_video_event(
            db,
            video,
            "video.ready",
            extra={"source": "live", "live_stream_id": stream.stream_id},
        )
    except Exception as exc:
        logger.warning("Live archive webhook failed: %s", exc)
    logger.info(
        "Archived live %s → VOD %s (%.1fs)",
        stream.stream_id,
        video.upload_id,
        duration or 0.0,
    )
    return video
