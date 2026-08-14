"""Normalize live ingest to H.264 + AAC HLS for Expo / MPEG-TS playback.

MediaMTX remuxes RTMP (already H.264/AAC) into ``LIVE_HLS_DIR/live/{key}``.
Browser WHIP typically publishes VP8+Opus, which crashes the MPEG-TS muxer.
This sidecar pulls RTSP from MediaMTX, transcodes only when needed, and writes
``LIVE_HLS_DIR/{stream_id}/index.m3u8`` — the same tree playback already
searches. WHEP on the ingest path is left untouched.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.live import mediamtx_client

logger = get_logger(__name__)

_VIDEO_PASSTHROUGH = frozenset({"h264", "avc", "h265", "hevc", "avc1"})
_AUDIO_PASSTHROUGH = frozenset(
    {"aac", "mpeg-4 audio", "mpeg4audio", "mpeg4-audio", "mp4a"}
)
_VIDEO_TRANSCODE = frozenset({"vp8", "vp9", "av1", "h263", "theora"})
_AUDIO_TRANSCODE = frozenset({"opus", "vorbis", "pcmu", "pcma", "g711", "speex"})

_processes: Dict[str, subprocess.Popen] = {}
_ll_processes: Dict[str, subprocess.Popen] = {}
_stops: Dict[str, threading.Event] = {}
_probing: Set[str] = set()
_lock = threading.Lock()


def is_enabled() -> bool:
    return bool(getattr(settings, "LIVE_NORMALIZE_ENABLED", True))


def extract_track_names(path_info: Optional[dict]) -> List[str]:
    if not path_info:
        return []
    raw = path_info.get("tracks") or []
    names: List[str] = []
    for item in raw:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            codec = item.get("codec") or item.get("codecName") or item.get("name")
            if codec:
                names.append(str(codec))
    return names


def _norm(name: str) -> str:
    return " ".join(name.lower().replace("_", "-").split())


def classify_tracks(tracks: Iterable[str]) -> dict:
    video_copy = False
    video_xcode = False
    audio_copy = False
    audio_xcode = False
    has_video = False
    has_audio = False
    for raw in tracks:
        n = _norm(raw)
        if n in _VIDEO_PASSTHROUGH or n in _VIDEO_TRANSCODE or "video" in n:
            has_video = True
        if n in _AUDIO_PASSTHROUGH or n in _AUDIO_TRANSCODE or "audio" in n or n == "opus":
            has_audio = True
        if n in _VIDEO_PASSTHROUGH:
            video_copy = True
        if n in _VIDEO_TRANSCODE:
            video_xcode = True
        if n in _AUDIO_PASSTHROUGH:
            audio_copy = True
        if n in _AUDIO_TRANSCODE:
            audio_xcode = True
        if n.startswith("vp8") or n.startswith("vp9"):
            video_xcode = True
            has_video = True
        if "opus" in n:
            audio_xcode = True
            has_audio = True
        if "h264" in n or n == "avc":
            video_copy = True
            has_video = True
        if "mpeg-4" in n or n == "aac":
            audio_copy = True
            has_audio = True
    return {
        "has_video": has_video,
        "has_audio": has_audio,
        "video_copy": video_copy and not video_xcode,
        "audio_copy": audio_copy and not audio_xcode,
        "needs_transcode": video_xcode or audio_xcode or (has_video and not video_copy),
    }


def tracks_need_transcode(tracks: Iterable[str]) -> bool:
    return bool(classify_tracks(tracks)["needs_transcode"])


def _rtsp_url(stream_key: str) -> str:
    base = (settings.MEDIAMTX_RTSP_URL or "rtsp://127.0.0.1:8554").rstrip("/")
    key = (stream_key or "").strip().strip("/")
    return f"{base}/live/{key}"


def _out_dir(stream_id: str) -> Path:
    path = Path(settings.LIVE_HLS_DIR) / stream_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clear_dir(stream_id: str) -> None:
    path = Path(settings.LIVE_HLS_DIR) / stream_id
    if not path.is_dir():
        return
    for child in path.iterdir():
        try:
            if child.is_file():
                child.unlink()
        except OSError:
            pass


def ll_enabled() -> bool:
    return bool(getattr(settings, "LIVE_LL_HLS_ENABLED", True)) and is_enabled()


def ll_dir(stream_id: str, *, create: bool = True) -> Path:
    path = Path(settings.LIVE_HLS_DIR) / stream_id / "ll"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def ll_playlist(stream_id: str, *, create: bool = False) -> Path:
    return ll_dir(stream_id, create=create) / "index.m3u8"


def ll_available(stream_id: str) -> bool:
    path = ll_playlist(stream_id, create=False)
    return path.is_file() and path.stat().st_size > 0


def _live_segment_seconds() -> int:
    return max(1, int(getattr(settings, "LIVE_HLS_SEGMENT_SECONDS", 1) or 1))


def _ffmpeg_cmd(
    stream_key: str,
    out: Path,
    *,
    copy_video: bool,
    copy_audio: bool,
    ll: bool = False,
) -> List[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise FileNotFoundError("ffmpeg")
    seg_n = _live_segment_seconds()
    seg = str(seg_n)
    # Copying H.264 keeps the encoder GOP (often 2–3s). 1s HLS needs an IDR
    # every segment, so re-encode when the live segment is short.
    if copy_video and seg_n <= 2:
        copy_video = False
    gop = str(max(12, seg_n * 30))
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-fflags",
        "+genpts",
        "-flags",
        "low_delay",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        "5000000",
        "-i",
        _rtsp_url(stream_key),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
    ]
    hw = (settings.FFMPEG_HWACCEL or "").strip()
    if copy_video:
        cmd.extend(["-c:v", "copy"])
    else:
        if hw:
            cmd.extend(["-hwaccel", hw])
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-tune",
                "zerolatency",
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
            ]
        )
    if copy_audio:
        cmd.extend(["-c:a", "copy"])
    else:
        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "48000"])
    cmd.extend(
        [
            "-max_delay",
            "0",
            "-muxdelay",
            "0",
            "-f",
            "hls",
        ]
    )
    if ll:
        part = max(0.2, float(getattr(settings, "LIVE_LL_HLS_PART_SECONDS", 0.33) or 0.33))
        cmd.extend(
            [
                "-hls_time",
                seg,
                "-hls_list_size",
                "15",
                "-hls_segment_type",
                "fmp4",
                "-hls_fmp4_init_filename",
                "init.mp4",
                "-hls_part_size",
                f"{part:.3f}",
                "-hls_flags",
                "delete_segments+independent_segments+omit_endlist+program_date_time+split_by_time+temp_file",
                "-hls_segment_filename",
                str(out / "seg_%05d.m4s"),
                str(out / "index.m3u8"),
            ]
        )
    else:
        cmd.extend(
            [
                "-hls_time",
                seg,
                "-hls_init_time",
                seg,
                "-hls_list_size",
                "3",
                "-hls_flags",
                "delete_segments+independent_segments+omit_endlist+split_by_time",
                "-hls_segment_filename",
                str(out / "seg_%05d.ts"),
                str(out / "index.m3u8"),
            ]
        )
    return cmd


def _kill_proc(stream_id: str, *, ll: bool = False) -> None:
    store = _ll_processes if ll else _processes
    with _lock:
        proc = store.pop(stream_id, None)
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
        logger.warning("Error stopping live normalize for %s: %s", stream_id, exc)


def _spawn(
    stream_id: str,
    stream_key: str,
    copy_video: bool,
    copy_audio: bool,
    *,
    ll: bool = False,
) -> None:
    _kill_proc(stream_id, ll=ll)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg not found; cannot normalize live %s", stream_id)
        return
    out = ll_dir(stream_id) if ll else _out_dir(stream_id)
    cmd = _ffmpeg_cmd(
        stream_key, out, copy_video=copy_video, copy_audio=copy_audio, ll=ll
    )
    kwargs = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        logger.warning("Failed to start live normalize for %s: %s", stream_id, exc)
        return
    store = _ll_processes if ll else _processes
    with _lock:
        store[stream_id] = proc
    logger.info(
        "Live normalize started for %s (copy_video=%s copy_audio=%s ll=%s) → %s",
        stream_id,
        copy_video,
        copy_audio,
        ll,
        out / "index.m3u8",
    )


def _probe_and_run(stream_id: str, stream_key: str, stop: threading.Event) -> None:
    attempts = max(1, int(getattr(settings, "LIVE_NORMALIZE_POLL_ATTEMPTS", 20)))
    interval = float(getattr(settings, "LIVE_NORMALIZE_POLL_INTERVAL", 0.4))
    path_name = f"live/{stream_key}"
    tracks: List[str] = []
    source_type = ""
    try:
        for _ in range(attempts):
            if stop.is_set():
                return
            info = mediamtx_client.get_path(path_name)
            source = (info or {}).get("source") or {}
            if isinstance(source, dict):
                source_type = str(source.get("type") or source_type)
            tracks = extract_track_names(info)
            if tracks:
                break
            stop.wait(interval)
        if stop.is_set():
            return
        classified = classify_tracks(tracks) if tracks else {
            "has_video": False,
            "has_audio": False,
            "video_copy": False,
            "audio_copy": False,
            "needs_transcode": True,
        }
        webrtc = "webRTC" in source_type or "whip" in source_type.lower()
        copy_v = bool(classified["video_copy"]) if tracks else (not webrtc)
        copy_a = bool(classified["audio_copy"]) if tracks else (not webrtc)
        if ll_enabled():
            logger.info(
                "Live LL-HLS mux for %s tracks=%s",
                stream_id,
                ", ".join(tracks) or source_type or "unknown",
            )
            _spawn(
                stream_id,
                stream_key,
                copy_video=copy_v,
                copy_audio=copy_a,
                ll=True,
            )
        if settings.LIVE_ABR_ENABLED:
            return
        if not tracks:
            # WHIP often lists tracks a beat after auth; RTMP is usually already muxable.
            if "webRTC" in source_type or "whip" in source_type.lower():
                logger.info(
                    "No tracks yet for %s (%s); normalizing WebRTC ingest",
                    stream_id,
                    source_type,
                )
                _spawn(stream_id, stream_key, copy_video=False, copy_audio=False)
            else:
                logger.debug(
                    "Live normalize passthrough for %s (no tracks, source=%s)",
                    stream_id,
                    source_type or "unknown",
                )
                _clear_dir(stream_id)
            return
        classified = classify_tracks(tracks)
        if not classified["needs_transcode"]:
            logger.info(
                "Live ingest already H.264/AAC for %s (%s); remux only",
                stream_id,
                ", ".join(tracks),
            )
            _clear_dir(stream_id)
            return
        logger.info(
            "Live normalize required for %s tracks=%s",
            stream_id,
            ", ".join(tracks),
        )
        _spawn(
            stream_id,
            stream_key,
            copy_video=bool(classified["video_copy"]),
            copy_audio=bool(classified["audio_copy"]),
        )
    finally:
        with _lock:
            _probing.discard(stream_id)


def start_normalize(stream_id: str, stream_key: str) -> None:
    """Non-blocking: poll MediaMTX tracks, spawn FFmpeg only when needed."""
    if not is_enabled():
        return
    if not stream_id or not stream_key:
        return
    with _lock:
        if stream_id in _probing or normalize_running(stream_id):
            return
        _probing.add(stream_id)
        stop = threading.Event()
        _stops[stream_id] = stop
    thread = threading.Thread(
        target=_probe_and_run,
        args=(stream_id, stream_key, stop),
        name=f"live-norm-{stream_id}",
        daemon=True,
    )
    thread.start()


def stop_normalize(stream_id: str) -> None:
    with _lock:
        stop = _stops.pop(stream_id, None)
        _probing.discard(stream_id)
    if stop is not None:
        stop.set()
    _kill_proc(stream_id, ll=False)
    _kill_proc(stream_id, ll=True)


def normalize_running(stream_id: str) -> bool:
    classic = _processes.get(stream_id)
    ll = _ll_processes.get(stream_id)
    return (classic is not None and classic.poll() is None) or (
        ll is not None and ll.poll() is None
    )
