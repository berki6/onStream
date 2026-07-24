"""Thumbnail generation via ffmpeg."""

from __future__ import annotations

import subprocess
from typing import Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.utils.paths import ensure_dir, to_relative_path

logger = get_logger(__name__)


def generate_thumbnail(video_path: str, video_id: int) -> Optional[str]:
    thumbnail_path = settings.VIDEO_THUMBNAIL_DIR / f"{video_id}.jpg"
    try:
        ensure_dir(thumbnail_path)
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            (
                f"thumbnail,scale={settings.THUMBNAIL_WIDTH}:{settings.THUMBNAIL_HEIGHT}"
                f":force_original_aspect_ratio=decrease,"
                f"pad={settings.THUMBNAIL_WIDTH}:{settings.THUMBNAIL_HEIGHT}:(ow-iw)/2:(oh-ih)/2"
            ),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(thumbnail_path),
            "-y",
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return to_relative_path(thumbnail_path)
    except Exception as e:
        logger.error(f"Thumbnail generation failed for video {video_id}: {e}")
        return None
