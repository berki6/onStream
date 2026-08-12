"""Smart thumbnail + optional preview clip selection."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional, Tuple

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.media.ffmpeg import probe_duration
from src.utils.paths import ensure_dir, to_relative_path

logger = get_logger(__name__)


def _frame_contrast(raw_gray: bytes) -> float:
    if not raw_gray:
        return 0.0
    values = list(raw_gray)
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _numpy_contrast(frame) -> float:
    """Prefer OpenCV Laplacian variance; fall back to numpy variance."""
    try:
        from src.infrastructure.media.pyav_io import frame_laplacian_variance

        return frame_laplacian_variance(frame)
    except Exception:
        pass
    try:
        import numpy as np

        arr = np.asarray(frame, dtype=np.float64).ravel()
        if arr.size == 0:
            return 0.0
        mean = float(arr.mean())
        return float(((arr - mean) ** 2).mean())
    except Exception:
        return 0.0


def pick_best_frame_time(video_path: str, candidates: int = 8) -> float:
    """Pick a timestamp (seconds) with highest gray-scale contrast."""
    duration = probe_duration(video_path) or 10.0
    if duration <= 1:
        return 0.0

    best_t = max(0.5, duration * 0.1)
    best_score = -1.0

    if settings.MEDIA_PYAV_ENABLED:
        try:
            from src.infrastructure.media import pyav_io

            frames = pyav_io.sample_frames(video_path, sample_count=candidates)
            if frames:
                for i, frame in enumerate(frames):
                    t = (duration * (i + 1)) / (candidates + 1)
                    score = _numpy_contrast(frame)
                    if score > best_score:
                        best_score = score
                        best_t = t
                return best_t
        except Exception as e:
            logger.debug("PyAV smart thumbnail sampling fallback: %s", e)

    for i in range(candidates):
        t = (duration * (i + 1)) / (candidates + 1)
        cmd = [
            "ffmpeg",
            "-ss",
            str(t),
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-vf",
            "scale=64:36,format=gray",
            "-f",
            "rawvideo",
            "-",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, check=False)
            score = _frame_contrast(result.stdout or b"")
            if score > best_score:
                best_score = score
                best_t = t
        except Exception:
            continue
    return best_t


def write_smart_thumbnail(
    video_path: str,
    video_id: int,
    timestamp: Optional[float] = None,
) -> Optional[str]:
    """Write a smart thumbnail at the best (or given) timestamp. Returns relative path."""
    t = timestamp if timestamp is not None else pick_best_frame_time(video_path)
    thumbnail_path = settings.VIDEO_THUMBNAIL_DIR / f"{video_id}_smart.jpg"
    try:
        ensure_dir(thumbnail_path)
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(t),
            "-i",
            video_path,
            "-vf",
            (
                f"scale={settings.THUMBNAIL_WIDTH}:{settings.THUMBNAIL_HEIGHT}"
                f":force_original_aspect_ratio=decrease,"
                f"pad={settings.THUMBNAIL_WIDTH}:{settings.THUMBNAIL_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
            ),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(thumbnail_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return to_relative_path(thumbnail_path)
    except Exception as e:
        logger.error(f"Smart thumbnail failed for video {video_id}: {e}")
        return None


def write_preview_clip(
    video_path: str,
    output_path: str,
    start: Optional[float] = None,
    duration: float = 3.0,
) -> Optional[str]:
    """Write a short preview clip. Returns output_path on success."""
    t = start if start is not None else pick_best_frame_time(video_path)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            str(t),
            "-i",
            video_path,
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-an",
            "-pix_fmt",
            "yuv420p",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return str(out)
    except Exception as e:
        logger.warning(f"Preview clip failed: {e}")
        return None


def generate_smart_assets(
    video_path: str, video_id: int, upload_id: str
) -> Tuple[Optional[str], Optional[str]]:
    """
    Generate smart thumbnail and optional 3s preview.

    Returns (thumbnail_rel_path, preview_rel_path).
    """
    t = pick_best_frame_time(video_path)
    thumb = write_smart_thumbnail(video_path, video_id, timestamp=t)
    preview_abs = settings.VIDEO_HLS_DIR / upload_id / "preview.mp4"
    preview_abs.parent.mkdir(parents=True, exist_ok=True)
    preview = write_preview_clip(video_path, str(preview_abs), start=t, duration=3.0)
    preview_rel = to_relative_path(preview_abs) if preview else None
    return thumb, preview_rel
