"""Storyboard sprite + VTT generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from src.core.logger import get_logger
from src.utils.paths import to_relative_path

logger = get_logger(__name__)


def generate_storyboard(
    video_path: str, output_dir: Path, duration: float
) -> tuple[Optional[str], Optional[str]]:
    """Create a simple sprite sheet + VTT for scrubbing."""
    if not duration or duration <= 0:
        return None, None
    sprite_path = output_dir / "storyboard.jpg"
    vtt_path = output_dir / "storyboard.vtt"
    try:
        # One frame every ~10s, max 20 frames
        interval = max(2.0, min(10.0, duration / 10))
        tile_w, tile_h = 160, 90
        cmd = [
            "ffmpeg",
            "-i",
            video_path,
            "-vf",
            f"fps=1/{interval},scale={tile_w}:{tile_h},tile=5x4",
            "-frames:v",
            "1",
            "-y",
            str(sprite_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)

        lines = ["WEBVTT", ""]
        t = 0.0
        idx = 0
        cols, rows = 5, 4
        while t < duration and idx < cols * rows:
            end = min(duration, t + interval)
            col = idx % cols
            row = idx // cols
            x, y = col * tile_w, row * tile_h

            def fmt(sec: float) -> str:
                from src.infrastructure.media.captions import _format_vtt_timestamp

                return _format_vtt_timestamp(sec)

            lines.append(f"{fmt(t)} --> {fmt(end)}")
            lines.append(f"storyboard.jpg#xywh={x},{y},{tile_w},{tile_h}")
            lines.append("")
            t = end
            idx += 1
        vtt_path.write_text("\n".join(lines), encoding="utf-8")
        return to_relative_path(sprite_path), to_relative_path(vtt_path)
    except Exception as e:
        logger.warning(f"Storyboard generation failed: {e}")
        return None, None
