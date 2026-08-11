"""Mock captions provider."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.infrastructure.ai.captions.base import CaptionsProvider


class MockCaptionsProvider(CaptionsProvider):
    def transcribe(self, path: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        from src.infrastructure.media.captions import _mock_segments
        from src.infrastructure.media.ffmpeg import probe_duration

        duration = probe_duration(path) or 30.0
        return {"language": "en", "segments": _mock_segments(duration)}
