"""Live stream health checks (stale playlist detection)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db import models
from src.infrastructure.db.repositories import live_stream_repository
from src.infrastructure.media import live_abr
from src.infrastructure.webhooks.delivery import enqueue_event

logger = get_logger(__name__)


def playlist_age_seconds(path: Optional[Path]) -> Optional[float]:
    """
    Return age of a playlist file in seconds based on mtime.

    Optionally cross-checks m3u8 media sequence freshness when the ``m3u8``
    package is available. Returns ``None`` if the path is missing.
    """
    if path is None:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        age = max(0.0, time.time() - p.stat().st_mtime)
    except OSError:
        return None

    # Prefer mtime; if m3u8 parses and has no segments, treat as stale-ish signal
    try:
        import m3u8

        playlist = m3u8.load(str(p))
        if playlist.segments is not None and len(playlist.segments) == 0:
            # Empty media playlist — still use file age but log once at debug
            logger.debug("Empty m3u8 playlist at %s (age=%.1fs)", p, age)
    except Exception:
        pass
    return age


def _live_root() -> Path:
    root = Path(settings.LIVE_HLS_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _candidate_playlists(stream: models.LiveStream) -> List[Path]:
    root = _live_root()
    candidates: List[Path] = []
    if settings.LIVE_ABR_ENABLED and stream.abr_hls_path:
        abr_dir = root / stream.abr_hls_path
        candidates.extend([abr_dir / "master.m3u8", abr_dir / "index.m3u8"])
    if stream.hls_path:
        hls_dir = root / stream.hls_path
        candidates.extend([hls_dir / "master.m3u8", hls_dir / "index.m3u8"])
    candidates.extend(
        [
            root / stream.stream_id / "master.m3u8",
            root / stream.stream_id / "index.m3u8",
        ]
    )
    return candidates


def resolve_playlist_path(stream: models.LiveStream) -> Optional[Path]:
    """Return first existing playlist path for a live stream, or None."""
    for path in _candidate_playlists(stream):
        if path.is_file():
            return path
    return None


def get_health_snapshot(db: Session, stream: models.LiveStream) -> Dict[str, Any]:
    """Build a health snapshot dict for a live stream (owner API)."""
    playlist = resolve_playlist_path(stream)
    age = playlist_age_seconds(playlist)
    stale_limit = settings.LIVE_STALE_SECONDS
    is_stale = age is None or age > stale_limit
    return {
        "stream_id": stream.stream_id,
        "status": stream.status,
        "playlist_path": str(playlist) if playlist else None,
        "playlist_present": playlist is not None,
        "playlist_age_seconds": age,
        "stale_seconds_threshold": stale_limit,
        "is_stale": bool(stream.status == "live" and is_stale),
        "abr_running": live_abr.abr_running(stream.stream_id),
        "hls_path": stream.hls_path,
        "abr_hls_path": stream.abr_hls_path,
        "started_at": stream.started_at,
        "ended_at": stream.ended_at,
    }


def _mark_stale_ended(db: Session, stream: models.LiveStream, reason: str) -> None:
    from src.core import metrics as metrics_mod

    live_abr.stop_abr(stream.stream_id)
    # Soft-fail to idle so the stream remains visible/re-publishable.
    # Hard "ended" is reserved for explicit revoke/delete.
    stream = live_stream_repository.set_idle(db, stream)
    final_status = "idle"

    try:
        enqueue_event(
            db,
            stream.user_id,
            "live.ended",
            {
                "stream_id": stream.stream_id,
                "status": final_status,
                "reason": reason,
            },
        )
    except Exception as exc:
        logger.warning("Failed to enqueue live.ended for %s: %s", stream.stream_id, exc)

    try:
        metrics_mod.LIVE_STREAMS_STALE_TOTAL.labels(reason=reason).inc()
        metrics_mod.LIVE_STREAMS_ACTIVE.set(
            live_stream_repository.count_by_status(db, "live")
        )
    except Exception:
        pass

    logger.info(
        "Live health: marked %s as %s (%s)",
        stream.stream_id,
        final_status,
        reason,
    )


def _within_hls_grace(stream: models.LiveStream) -> bool:
    """Skip missing-playlist teardown while MediaMTX is still writing first segments."""
    started = stream.started_at
    if started is None:
        return False
    try:
        from datetime import datetime, timezone

        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - started).total_seconds()
    except Exception:
        return False
    grace = max(int(settings.LIVE_STALE_SECONDS), 15)
    return age < grace


def check_live_streams(db: Session) -> int:
    """
    Scan status=live streams; mark idle when playlist is missing or stale.

    Returns the number of streams transitioned.
    """
    if not settings.LIVE_HEALTH_ENABLED:
        return 0

    from src.core import metrics as metrics_mod

    live_rows = live_stream_repository.list_by_status(db, "live")
    try:
        metrics_mod.LIVE_STREAMS_ACTIVE.set(len(live_rows))
        metrics_mod.LIVE_ABR_ACTIVE.set(sum(1 for s in live_rows if live_abr.abr_running(s.stream_id)))
    except Exception:
        pass

    transitioned = 0
    for stream in live_rows:
        playlist = resolve_playlist_path(stream)
        age = playlist_age_seconds(playlist)

        if age is not None:
            try:
                metrics_mod.LIVE_PLAYLIST_AGE.observe(age)
            except Exception:
                pass

        if playlist is None:
            # HLS muxer needs a few seconds after publish auth before index.m3u8 exists.
            if _within_hls_grace(stream):
                logger.debug(
                    "Live health: %s missing playlist but within HLS grace; skipping",
                    stream.stream_id,
                )
                continue
            _mark_stale_ended(db, stream, "missing_playlist")
            transitioned += 1
            continue

        if age is not None and age > settings.LIVE_STALE_SECONDS:
            _mark_stale_ended(db, stream, "stale_playlist")
            transitioned += 1

    return transitioned
