"""ABR ladder selection and master playlist helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from src.core.config import settings


def select_ladder(source_height: int, ladder: Optional[List[dict]] = None) -> List[dict]:
    """Filter ABR ladder to rungs at or below source height."""
    rungs = ladder if ladder is not None else settings.abr_ladder_list
    selected = [r for r in rungs if r["height"] <= source_height]
    if not selected:
        selected = [{"height": min(720, source_height), "bitrate_k": 2800}]
    return selected


def write_master_playlist(output_dir: Path, renditions: List[Dict]) -> Path:
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    for r in renditions:
        bandwidth = r["bitrate_k"] * 1000
        height = r["height"]
        width = int(height * 16 / 9)
        lines.append(
            f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height}"
        )
        lines.append(f"{height}p/index.m3u8")
    master = output_dir / "master.m3u8"
    master.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return master
