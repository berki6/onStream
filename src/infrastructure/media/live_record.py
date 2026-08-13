"""Accumulate a full HLS archive while a live stream is up.

Live edge playback may use a sliding window. Archive HLS is an EVENT playlist
that keeps every segment so viewers can DVR-scrub and revoke can promote a VOD
without a second ABR transcode.

Reconnects must not reuse ``seg_00000.ts`` — that would overwrite bytes while
the playlist still points at the old names. ``start_number`` continues the
sequence. Video is always re-encoded so each segment starts on an IDR.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Dict, List, Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.live import mediamtx_client
from src.infrastructure.media import live_normalize as ln

logger = get_logger(__name__)

_processes: Dict[str, subprocess.Popen] = {}
_stops: Dict[str, threading.Event] = {}
_lock = threading.Lock()

_MASTER = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:BANDWIDTH=2500000
index.m3u8
"""


def is_enabled() -> bool:
    return bool(getattr(settings, "LIVE_ARCHIVE_ENABLED", True))


def archive_dir(stream_id: str, *, create: bool = True) -> Path:
    path = Path(settings.LIVE_HLS_DIR) / stream_id / "archive"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def archive_playlist(stream_id: str, *, create: bool = True) -> Path:
    return archive_dir(stream_id, create=create) / "index.m3u8"


def archive_master(stream_id: str, *, create: bool = True) -> Path:
    return archive_dir(stream_id, create=create) / "master.m3u8"


def _archive_segment_seconds() -> int:
    return max(2, int(getattr(settings, "LIVE_ARCHIVE_SEGMENT_SECONDS", 4) or 4))


def next_segment_index(out: Path) -> int:
    """Continue ``seg_%05d.ts`` after the highest existing index (reconnect-safe)."""
    highest = -1
    if not out.is_dir():
        return 0
    for child in out.glob("seg_*.ts"):
        stem = child.stem
        if not stem.startswith("seg_"):
            continue
        suffix = stem[4:]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return highest + 1


def playlist_media_duration(playlist: Path) -> Optional[float]:
    """Sum #EXTINF durations. Avoids a blocking ffprobe on the control path."""
    if not playlist.is_file():
        return None
    total = 0.0
    found = False
    try:
        text = playlist.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("#EXTINF:"):
            continue
        payload = line.split(":", 1)[1]
        token = payload.split(",", 1)[0].strip()
        try:
            total += float(token)
            found = True
        except ValueError:
            continue
    if not found or total <= 0:
        return None
    return total


def _segment_names(text: str) -> List[str]:
    names: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        names.append(Path(line.split("?", 1)[0]).name)
    return names


def playlist_has_segments(playlist: Path) -> bool:
    """True only when the playlist cites at least one existing non-empty segment."""
    if not playlist.is_file():
        return False
    try:
        text = playlist.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    if "#EXTINF" not in text:
        return False
    parent = playlist.parent
    for name in _segment_names(text):
        if not name or name.endswith(".m3u8"):
            continue
        path = parent / name
        try:
            if path.is_file() and path.stat().st_size > 0:
                return True
        except OSError:
            continue
    return False


def _kill_proc(stream_id: str) -> None:
    with _lock:
        proc = _processes.pop(stream_id, None)
    if proc is None:
        return
    try:
        if proc.poll() is None:
            try:
                if proc.stdin:
                    proc.stdin.write(b"q\n")
                    proc.stdin.flush()
                    proc.stdin.close()
            except Exception:
                pass
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
    except Exception as exc:  # pragma: no cover
        logger.warning("Error stopping live archive for %s: %s", stream_id, exc)


def _ffmpeg_cmd(
    stream_key: str,
    out: Path,
    *,
    copy_audio: bool,
    start_number: int = 0,
) -> List[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg")
    seg_n = _archive_segment_seconds()
    seg = str(seg_n)
    gop = str(max(24, seg_n * 30))
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "+genpts",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        "5000000",
        "-i",
        ln._rtsp_url(stream_key),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-g",
        gop,
        "-keyint_min",
        gop,
        "-sc_threshold",
        "0",
        "-bf",
        "0",
        "-force_key_frames",
        f"expr:gte(t,n_forced*{seg_n})",
    ]
    if copy_audio:
        cmd.extend(["-c:a", "copy"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "48000"])
    cmd.extend(
        [
            "-f",
            "hls",
            "-hls_time",
            seg,
            "-hls_list_size",
            "0",
            "-hls_playlist_type",
            "event",
            "-start_number",
            str(max(0, int(start_number))),
            "-hls_flags",
            "independent_segments+append_list+program_date_time+split_by_time",
            "-hls_segment_filename",
            str(out / "seg_%05d.ts"),
            str(out / "index.m3u8"),
        ]
    )
    return cmd


def _write_master(out: Path) -> None:
    master = out / "master.m3u8"
    if not master.is_file():
        master.write_text(_MASTER, encoding="utf-8")


def _spawn(stream_id: str, stream_key: str, copy_audio: bool) -> None:
    _kill_proc(stream_id)
    if not shutil.which("ffmpeg"):
        logger.warning("ffmpeg not found; cannot archive live %s", stream_id)
        return
    out = archive_dir(stream_id)
    _strip_endlist(out / "index.m3u8")
    _write_master(out)
    start_number = next_segment_index(out)
    try:
        cmd = _ffmpeg_cmd(
            stream_key, out, copy_audio=copy_audio, start_number=start_number
        )
    except FileNotFoundError:
        return
    kwargs = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        logger.warning("Failed to start live archive for %s: %s", stream_id, exc)
        return
    with _lock:
        _processes[stream_id] = proc
    logger.info(
        "Live archive started for %s start_number=%s → %s",
        stream_id,
        start_number,
        out / "index.m3u8",
    )


def _probe_and_run(stream_id: str, stream_key: str, stop: threading.Event) -> None:
    attempts = max(1, int(getattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 20)))
    interval = float(getattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", "0.4"))
    tracks: List[str] = []
    source_type = ""
    try:
        for _ in range(attempts):
            if stop.is_set():
                return
            info = mediamtx_client.get_path(f"live/{stream_key}")
            source = (info or {}).get("source") or {}
            if isinstance(source, dict):
                source_type = str(source.get("type") or source_type)
            tracks = ln.extract_track_names(info)
            if tracks:
                break
            stop.wait(interval)
        if stop.is_set():
            return
        copy_audio = False
        if not tracks:
            if "webRTC" in source_type or "whip" in source_type.lower():
                _spawn(stream_id, stream_key, copy_audio=False)
            return
        classified = ln.classify_tracks(tracks)
        copy_audio = bool(classified["audio_copy"])
        _spawn(stream_id, stream_key, copy_audio=copy_audio)
    finally:
        pass


def start_record(stream_id: str, stream_key: str) -> None:
    if not is_enabled() or not stream_id or not stream_key:
        return
    with _lock:
        if record_running(stream_id):
            return
        stale = _stops.pop(stream_id, None)
        if stale is not None:
            stale.set()
        stop = threading.Event()
        _stops[stream_id] = stop
    thread = threading.Thread(
        target=_probe_and_run,
        args=(stream_id, stream_key, stop),
        name=f"live-archive-{stream_id}",
        daemon=True,
    )
    thread.start()


def finalize_playlist(playlist: Path) -> None:
    if not playlist.is_file():
        return
    text = playlist.read_text(encoding="utf-8", errors="ignore")
    if "#EXT-X-ENDLIST" not in text:
        if text and not text.endswith("\n"):
            text += "\n"
        text += "#EXT-X-ENDLIST\n"
    text = text.replace("#EXT-X-PLAYLIST-TYPE:EVENT", "#EXT-X-PLAYLIST-TYPE:VOD")
    playlist.write_text(text, encoding="utf-8")


def _strip_endlist(playlist: Path) -> None:
    if not playlist.is_file():
        return
    text = playlist.read_text(encoding="utf-8", errors="ignore")
    if "#EXT-X-ENDLIST" not in text:
        return
    text = text.replace("#EXT-X-ENDLIST\n", "").replace("#EXT-X-ENDLIST", "")
    text = text.replace("#EXT-X-PLAYLIST-TYPE:VOD", "#EXT-X-PLAYLIST-TYPE:EVENT")
    playlist.write_text(text, encoding="utf-8")


def stop_record(stream_id: str, *, finalize: bool = True) -> None:
    with _lock:
        stop = _stops.pop(stream_id, None)
    if stop is not None:
        stop.set()
    _kill_proc(stream_id)
    if not finalize:
        return
    try:
        finalize_playlist(archive_playlist(stream_id, create=False))
    except OSError:
        pass


def record_running(stream_id: str) -> bool:
    proc = _processes.get(stream_id)
    return proc is not None and proc.poll() is None
