"""Moderation provider protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class ModerationProvider(ABC):
    @abstractmethod
    def score(
        self,
        *,
        transcript_text: str = "",
        video_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return {"score": float, "labels": list[str]}."""
