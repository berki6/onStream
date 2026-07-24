"""QoE canary: poll live playlist age and local fetch latency."""

from __future__ import annotations

import time

from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.db.repositories import live_stream_repository
from src.infrastructure.live.health import playlist_age_seconds, resolve_playlist_path

logger = get_logger(__name__)


def run_qoe_canary(db: Session) -> int:
    """
    Sample live streams' playlist age + local file read timing.

    Records histograms when metrics are available. Returns samples counted.
    """
    if not settings.QOE_CANARY_ENABLED:
        return 0

    from src.core import metrics as metrics_mod

    rows = live_stream_repository.list_by_status(db, "live")
    counted = 0
    for stream in rows:
        path = resolve_playlist_path(stream)
        age = playlist_age_seconds(path)
        if age is not None:
            try:
                metrics_mod.QOE_PLAYLIST_AGE.observe(age)
            except Exception:
                pass

        if path is not None and path.is_file():
            t0 = time.perf_counter()
            try:
                _ = path.read_bytes()
            except OSError as exc:
                logger.debug("QoE canary read failed for %s: %s", path, exc)
                continue
            elapsed = time.perf_counter() - t0
            try:
                metrics_mod.QOE_FETCH_LATENCY.observe(elapsed)
            except Exception:
                pass
            counted += 1
        elif age is not None:
            counted += 1

    return counted
