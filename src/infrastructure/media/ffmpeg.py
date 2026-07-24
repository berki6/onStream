"""FFmpeg helpers for probing and encoding."""

from __future__ import annotations

import subprocess
from pathlib import Path


def extract_concise_error(stderr_text: str, max_lines=3, max_length=250) -> str:
    if not stderr_text:
        return "Unknown error (stderr is empty)"
    lines = stderr_text.strip().splitlines()
    error_keywords = [
        "error",
        "invalid",
        "fail",
        "could not",
        "no such",
        "denied",
        "unsupported",
        "unable",
        "can't open",
        "conversion failed",
    ]
    start = max(0, len(lines) - max_lines)
    for i in range(len(lines) - 1, start - 1, -1):
        line = lines[i].strip()
        if not line:
            continue
        if any(keyword in line.lower() for keyword in error_keywords):
            if i > 0 and lines[i - 1].strip():
                return f"{lines[i-1].strip()}\n{line}"[:max_length]
            return line[:max_length]
    for line in reversed(lines):
        if line.strip():
            return line[:max_length]
    return "Unknown error (no specific issue found)"


def probe_height(video_path: str) -> int:
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "csv=p=0",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(result.stdout.strip().splitlines()[0])
    except Exception:
        return 720


def probe_duration(video_path: str) -> float:
    """Return media duration in seconds, or 0.0 on failure."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip().splitlines()[0])
    except Exception:
        return 0.0


def encode_rendition(
    upload_file: Path,
    rendition_dir: Path,
    height: int,
    bitrate_k: int,
    segment_seconds: int,
) -> None:
    rendition_dir.mkdir(parents=True, exist_ok=True)
    gop = segment_seconds * 30  # assume ~30fps
    cmd = [
        "ffmpeg",
        "-i",
        str(upload_file),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-profile:v",
        "main",
        "-b:v",
        f"{bitrate_k}k",
        "-maxrate",
        f"{int(bitrate_k * 1.07)}k",
        "-bufsize",
        f"{bitrate_k * 2}k",
        "-vf",
        f"scale=-2:{height}",
        "-x264-params",
        f"keyint={gop}:min-keyint={gop}:scenecut=0",
        "-force_key_frames",
        f"expr:gte(t,n_forced*{segment_seconds})",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ac",
        "2",
        "-hls_time",
        str(segment_seconds),
        "-hls_playlist_type",
        "vod",
        "-hls_list_size",
        "0",
        "-hls_segment_filename",
        str(rendition_dir / "segment_%03d.ts"),
        "-f",
        "hls",
        str(rendition_dir / "index.m3u8"),
        "-y",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, cmd, stderr=result.stderr
        )
