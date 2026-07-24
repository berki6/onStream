"""Caption / transcription helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.media.ffmpeg import probe_duration

logger = get_logger(__name__)


def extract_audio(video_path: str, audio_path: str) -> str:
    """Extract mono 16kHz WAV audio via ffmpeg. Returns audio_path."""
    out = Path(audio_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        video_path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return str(out)


def _format_vtt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def segments_to_vtt(segments: List[Dict[str, Any]]) -> str:
    """Convert [{start, end, text}, ...] to WebVTT."""
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments, start=1):
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start + 1))
        text = str(seg.get("text", "")).strip()
        lines.append(str(i))
        lines.append(
            f"{_format_vtt_timestamp(start)} --> {_format_vtt_timestamp(end)}"
        )
        lines.append(text or "...")
        lines.append("")
    return "\n".join(lines)


def _mock_segments(duration: float) -> List[Dict[str, Any]]:
    """Deterministic fake segments for CI / mock provider."""
    duration = max(duration, 3.0)
    chunk = max(duration / 3.0, 1.0)
    texts = [
        "Welcome to this video.",
        "Here we discuss the main topic.",
        "Thank you for watching.",
    ]
    segments = []
    t = 0.0
    for i, text in enumerate(texts):
        end = min(t + chunk, duration)
        segments.append({"start": t, "end": end, "text": text})
        t = end
        if t >= duration:
            break
    if not segments:
        segments = [{"start": 0.0, "end": duration, "text": "Audio content."}]
    return segments


def transcribe(
    path: str,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcribe audio/video path.

    Returns {"language": str, "segments": [{"start","end","text"}, ...]}.
    Falls back to mock when provider=mock or faster_whisper is unavailable.
    """
    provider = (provider or settings.AI_CAPTIONS_PROVIDER or "mock").lower()
    duration = probe_duration(path) or 30.0

    if provider == "mock":
        return {"language": "en", "segments": _mock_segments(duration)}

    if provider == "faster_whisper":
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
                segments = _mock_segments(duration)
            lang = getattr(info, "language", None) or "en"
            return {"language": lang, "segments": segments}
        except Exception as e:
            logger.warning(f"faster_whisper unavailable, using mock: {e}")
            return {"language": "en", "segments": _mock_segments(duration)}

    logger.warning(f"Unknown captions provider '{provider}', using mock")
    return {"language": "en", "segments": _mock_segments(duration)}
