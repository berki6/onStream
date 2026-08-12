"""Optional live ABR ladder via FFmpeg (gated by LIVE_ABR_ENABLED)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

# In-memory process registry: stream_id → Popen
_processes: Dict[str, subprocess.Popen] = {}


def is_abr_enabled() -> bool:
    return bool(settings.LIVE_ABR_ENABLED)


def start_abr(
    stream_id: str,
    stream_key: str,
    output_dir: Optional[Path] = None,
) -> Optional[subprocess.Popen]:
    """
    Start an FFmpeg ABR ladder from MediaMTX RTMP.

    No-op when LIVE_ABR_ENABLED is false, ffmpeg is missing, or spawn fails.
    """
    if not settings.LIVE_ABR_ENABLED:
        logger.debug("LIVE_ABR_ENABLED=false; skipping ABR for %s", stream_id)
        return None

    stop_abr(stream_id)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg not found; skipping live ABR for %s", stream_id)
        return None

    out = output_dir or (settings.LIVE_HLS_DIR / stream_id / "abr")
    out.mkdir(parents=True, exist_ok=True)

    rtmp_base = settings.MEDIAMTX_RTMP_URL.rstrip("/")
    # Prefer docker-internal host when URL points at localhost
    source = f"{rtmp_base}/{stream_key}"

    ladder = settings.live_abr_ladder_list
    if not ladder:
        ladder = [{"height": 720, "bitrate_k": 2500}]

    # Build a simple single-rendition or multi-output command.
    # For multi-rung we write separate playlists and a master.
    filter_parts = []
    map_args = []
    var_stream_map = []
    for i, rung in enumerate(ladder):
        h = rung["height"]
        br = rung["bitrate_k"]
        filter_parts.append(f"[0:v]scale=-2:{h}[v{i}]")
        map_args.extend(["-map", f"[v{i}]", "-map", "0:a?"])
        var_stream_map.append(f"v:{i},a:{i},name:{h}p")
        map_args.extend(
            [
                f"-b:v:{i}",
                f"{br}k",
                f"-maxrate:v:{i}",
                f"{int(br * 1.07)}k",
                f"-bufsize:v:{i}",
                f"{br * 2}k",
            ]
        )

    filter_complex = ";".join(filter_parts)
    master = out / "master.m3u8"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        source,
        "-filter_complex",
        filter_complex,
        *map_args,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-c:a",
        "aac",
        "-f",
        "hls",
        "-hls_time",
        str(settings.HLS_SEGMENT_SECONDS),
        "-hls_list_size",
        "6",
        "-hls_flags",
        "delete_segments+independent_segments",
        "-master_pl_name",
        "master.m3u8",
        "-var_stream_map",
        " ".join(var_stream_map),
        str(out / "%v" / "index.m3u8"),
    ]

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        logger.warning("Failed to start live ABR for %s: %s", stream_id, exc)
        return None

    _processes[stream_id] = proc
    logger.info("Started live ABR for %s → %s", stream_id, master)
    return proc


def stop_abr(stream_id: str) -> None:
    proc = _processes.pop(stream_id, None)
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Error stopping ABR for %s: %s", stream_id, exc)


def abr_running(stream_id: str) -> bool:
    proc = _processes.get(stream_id)
    return proc is not None and proc.poll() is None
