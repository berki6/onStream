"""Content moderation scoring (keyword + frame heuristics)."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.core.logger import get_logger

logger = get_logger(__name__)

# Simple keyword denylist for mock/heuristic moderation
_FLAGGED_KEYWORDS = [
    "violence",
    "gore",
    "explicit",
    "nsfw",
    "hate",
    "terror",
    "weapon",
    "abuse",
    "suicide",
    "self-harm",
]


def score_transcript(text: str) -> Tuple[float, List[str]]:
    """Score transcript text against flagged keywords. Returns (score, labels)."""
    if not text:
        return 0.0, []
    lowered = text.lower()
    labels = []
    for kw in _FLAGGED_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", lowered):
            labels.append(kw)
    if not labels:
        return 0.0, []
    # Cap at 1.0; more matches => higher score
    score = min(1.0, 0.35 + 0.2 * len(labels))
    return score, labels


def score_frames(video_path: str, sample_count: int = 5) -> Tuple[float, List[str]]:
    """
    Heuristic frame scoring via luminance variance sampling.

    High variance alone is not flagged; extremely dark/near-black frames
    contribute a mild score. Falls back to (0.0, []) on ffmpeg failure.
    """
    path = Path(video_path)
    if not path.exists():
        return 0.0, []

    try:
        # Sample a few frames as raw gray and measure mean intensity
        cmd = [
            "ffmpeg",
            "-i",
            str(path),
            "-vf",
            f"fps=1/{max(sample_count, 1)},scale=64:36,format=gray",
            "-frames:v",
            str(sample_count),
            "-f",
            "rawvideo",
            "-",
        ]
        result = subprocess.run(cmd, capture_output=True, check=False)
        data = result.stdout or b""
        if not data:
            return 0.0, []
        values = list(data)
        if not values:
            return 0.0, []
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        labels: List[str] = []
        score = 0.0
        # Near-black content is a weak signal only
        if mean < 15:
            score = 0.25
            labels.append("low_luminance")
        if variance < 5 and mean < 30:
            score = max(score, 0.35)
            labels.append("uniform_dark")
        return score, labels
    except Exception as e:
        logger.warning(f"Frame moderation failed for {video_path}: {e}")
        return 0.0, []


def combine_scores(
    transcript_score: float,
    transcript_labels: List[str],
    frame_score: float = 0.0,
    frame_labels: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Combine transcript + frame scores into a single moderation result."""
    frame_labels = frame_labels or []
    # Transcript dominates; frames contribute lightly
    combined = min(1.0, max(transcript_score, 0.6 * transcript_score + 0.4 * frame_score))
    labels = list(dict.fromkeys([*transcript_labels, *frame_labels]))
    return {"score": combined, "labels": labels}
