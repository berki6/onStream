"""faster-whisper captions provider."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.ai.captions.base import CaptionsProvider
from src.infrastructure.ai.policy import fail_closed

logger = get_logger(__name__)


class FasterWhisperCaptionsProvider(CaptionsProvider):
    def transcribe(self, path: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        from src.infrastructure.ai.captions.mock import MockCaptionsProvider
        from src.infrastructure.media.ffmpeg import probe_duration

        try:
            from faster_whisper import WhisperModel  # type: ignore

            model = WhisperModel(
                model_name or settings.WHISPER_MODEL, device="cpu", compute_type="int8"
            )
            segments_iter, info = model.transcribe(path, beam_size=1)
            segments = [
                {
                    "start": float(s.start),
                    "end": float(s.end),
                    "text": (s.text or "").strip(),
                }
                for s in segments_iter
            ]
            if not segments:
                duration = probe_duration(path) or 0.0
                logger.warning(
                    "faster_whisper returned no segments for %s (duration=%.1fs)",
                    path,
                    duration,
                )
            lang = getattr(info, "language", None) or "en"
            return {"language": lang, "segments": segments}
        except Exception as e:
            if fail_closed():
                raise
            logger.warning("faster_whisper unavailable, using mock: %s", e)
            return MockCaptionsProvider().transcribe(path, model_name)
