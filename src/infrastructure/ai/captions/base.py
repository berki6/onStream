"""Captions provider protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class CaptionsProvider(ABC):
    @abstractmethod
    def transcribe(self, path: str, model_name: str | None = None) -> Dict[str, Any]:
        """Return {"language": str, "segments": [{"start","end","text"}, ...]}."""
