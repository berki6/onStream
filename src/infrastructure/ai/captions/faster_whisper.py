"""faster-whisper captions provider."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.ai.captions.base import CaptionsProvider
from src.infrastructure.ai.policy import fail_closed
from src.infrastructure.media.captions import normalize_segments

logger = get_logger(__name__)


def _unpack_transcribe_result(raw: Any) -> tuple[Any, Any]:
    """
    faster-whisper returns (segments_iterable, info).

    Guard against odd return shapes / accidental wrapping so callers never see
    a naked ``ValueError: too many values to unpack``.
    """
    if isinstance(raw, tuple) and len(raw) == 2:
        return raw[0], raw[1]
    if isinstance(raw, list) and len(raw) == 2:
        return raw[0], raw[1]
    # Single iterable of segments (no info object)
    return raw, None


class FasterWhisperCaptionsProvider(CaptionsProvider):
    def transcribe(self, path: str, model_name: Optional[str] = None) -> Dict[str, Any]:
        from src.infrastructure.ai.captions.mock import MockCaptionsProvider
        from src.infrastructure.media.ffmpeg import probe_duration

        try:
            from faster_whisper import WhisperModel  # type: ignore

            model = WhisperModel(
                model_name or settings.WHISPER_MODEL, device="cpu", compute_type="int8"
            )
            raw = model.transcribe(path, beam_size=1)
            segments_iter, info = _unpack_transcribe_result(raw)
            segments = normalize_segments(list(segments_iter) if segments_iter else [])
            if not segments:
                duration = probe_duration(path) or 0.0
                logger.warning(
                    "faster_whisper returned no segments for %s (duration=%.1fs)",
                    path,
                    duration,
                )
            lang = "en"
            if info is not None:
                lang = str(getattr(info, "language", None) or "en")
            return {"language": lang, "segments": segments}
        except Exception as e:
            if fail_closed():
                raise
            logger.warning("faster_whisper unavailable, using mock: %s", e)
            return MockCaptionsProvider().transcribe(path, model_name)
