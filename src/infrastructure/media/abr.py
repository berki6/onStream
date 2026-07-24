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


def write_master_playlist(
    output_dir: Path,
    renditions: List[Dict],
    captions_uri: Optional[str] = None,
) -> Path:
    lines = ["#EXTM3U", "#EXT-X-VERSION:3"]
    if captions_uri:
        lines.append(
            '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Captions",'
            f'DEFAULT=YES,AUTOSELECT=YES,URI="{captions_uri}"'
        )
    for r in renditions:
        bandwidth = r["bitrate_k"] * 1000
        height = r["height"]
        width = int(height * 16 / 9)
        stream_inf = (
            f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={width}x{height}"
        )
        if captions_uri:
            stream_inf += ',SUBTITLES="subs"'
        lines.append(stream_inf)
        lines.append(f"{height}p/index.m3u8")
    master = output_dir / "master.m3u8"
    master.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return master


def inject_subtitle_track(playlist: str, captions_uri: str = "captions.vtt") -> str:
    """Inject subtitle MEDIA tag into an existing master playlist if missing."""
    if "TYPE=SUBTITLES" in playlist:
        return playlist

    try:
        import m3u8

        pl = m3u8.loads(playlist)
        # Add subtitle media tag
        media_tag = m3u8.Media(
            type="SUBTITLES",
            group_id="subs",
            name="Captions",
            default="YES",
            autoselect="YES",
            uri=captions_uri,
        )
        pl.add_media(media_tag)
        for variant in pl.playlists or []:
            stream_info = variant.stream_info
            if stream_info is not None:
                # Ensure SUBTITLES group is referenced
                if not getattr(stream_info, "subtitles", None):
                    stream_info.subtitles = "subs"
        dumped = pl.dumps()
        if not dumped.endswith("\n"):
            dumped += "\n"
        # Ensure SUBTITLES="subs" appears on STREAM-INF lines (m3u8 may not always emit)
        if 'SUBTITLES="subs"' not in dumped:
            lines = []
            for line in dumped.splitlines():
                if line.startswith("#EXT-X-STREAM-INF:") and 'SUBTITLES="subs"' not in line:
                    lines.append(line.rstrip() + ',SUBTITLES="subs"')
                else:
                    lines.append(line)
            dumped = "\n".join(lines) + "\n"
        return dumped
    except Exception:
        pass

    # Fallback: line-based injection
    lines = playlist.splitlines()
    out: List[str] = []
    media_inserted = False
    for line in lines:
        if line.startswith("#EXTM3U"):
            out.append(line)
            continue
        if line.startswith("#EXT-X-VERSION"):
            out.append(line)
            if not media_inserted:
                out.append(
                    '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Captions",'
                    f'DEFAULT=YES,AUTOSELECT=YES,URI="{captions_uri}"'
                )
                media_inserted = True
            continue
        if line.startswith("#EXT-X-STREAM-INF:") and 'SUBTITLES="subs"' not in line:
            out.append(line.rstrip() + ',SUBTITLES="subs"')
            continue
        out.append(line)
    if not media_inserted:
        rebuilt = []
        for i, line in enumerate(out):
            rebuilt.append(line)
            if i == 0:
                rebuilt.append(
                    '#EXT-X-MEDIA:TYPE=SUBTITLES,GROUP-ID="subs",NAME="Captions",'
                    f'DEFAULT=YES,AUTOSELECT=YES,URI="{captions_uri}"'
                )
        out = rebuilt
    return "\n".join(out) + ("\n" if playlist.endswith("\n") or out else "")
