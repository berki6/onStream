"""Heuristic (local) moderation provider."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.infrastructure.ai.moderation.base import ModerationProvider
from src.infrastructure.media import moderation as heuristic


class HeuristicModerationProvider(ModerationProvider):
    def score(
        self,
        *,
        transcript_text: str = "",
        video_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        t_score, t_labels = heuristic.score_transcript(transcript_text or "")
        f_score, f_labels = (0.0, [])
        if video_path:
            f_score, f_labels = heuristic.score_frames(video_path)
        return heuristic.combine_scores(t_score, t_labels, f_score, f_labels)
