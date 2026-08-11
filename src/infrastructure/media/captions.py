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
    """Extract mono 16kHz WAV audio. Prefers PyAV when enabled; falls back to ffmpeg."""
    out = Path(audio_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    if settings.MEDIA_PYAV_ENABLED:
        try:
            from src.infrastructure.media import pyav_io

            return pyav_io.extract_audio_pcm_or_wav(
                video_path, str(out), sample_rate=16000, channels=1
            )
        except Exception as exc:
            logger.debug("PyAV audio extract failed, falling back to ffmpeg: %s", exc)

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
    """WebVTT cue time: HH:MM:SS.mmm (seconds always two digits before the dot)."""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000.0))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


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
    Transcribe audio/video path via the captions provider registry.

    Returns {"language": str, "segments": [{"start","end","text"}, ...]}.
    """
    from src.infrastructure.ai.registry import get_captions_provider

    return get_captions_provider(provider).transcribe(path, model_name=model_name)
