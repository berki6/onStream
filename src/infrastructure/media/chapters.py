"""Chapter detection from transcript segments."""

from __future__ import annotations

from typing import Any, Dict, List


def chapters_from_segments(
    segments: List[Dict[str, Any]], min_gap: float = 30.0
) -> List[Dict[str, Any]]:
    """
    Build chapters from timed transcript segments.

    Starts a new chapter when the gap between consecutive segments exceeds
    ``min_gap`` seconds, or at the first segment. Titles are derived from
    the first line of each chapter.
    """
    if not segments:
        return []

    chapters: List[Dict[str, Any]] = []
    current: Dict[str, Any] | None = None

    for seg in segments:
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start))
        text = str(seg.get("text", "")).strip()

        if current is None:
            current = {
                "start": start,
                "end": end,
                "title": (text[:80] or "Chapter 1"),
            }
            continue

        gap = start - float(current["end"])
        if gap >= min_gap:
            chapters.append(current)
            current = {
                "start": start,
                "end": end,
                "title": (text[:80] or f"Chapter {len(chapters) + 1}"),
            }
        else:
            current["end"] = max(float(current["end"]), end)

    if current is not None:
        chapters.append(current)

    # Ensure unique-ish titles
    for i, ch in enumerate(chapters, start=1):
        if not ch.get("title"):
            ch["title"] = f"Chapter {i}"

    return chapters
