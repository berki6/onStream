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


def normalize_segments(raw: Any) -> List[Dict[str, Any]]:
    """
    Coerce provider output into [{start, end, text}, ...].

    Drops junk rows; never raises on odd shapes.
    """
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = raw.get("segments", [])
    if not isinstance(raw, (list, tuple)):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        try:
            if isinstance(item, dict):
                start = float(item.get("start", 0) or 0)
                end = float(item.get("end", start + 1) or (start + 1))
                text = str(item.get("text", "") or "").strip()
            else:
                # NamedTuple / object with attributes (faster-whisper Segment)
                start = float(getattr(item, "start", 0) or 0)
                end = float(getattr(item, "end", start + 1) or (start + 1))
                text = str(getattr(item, "text", "") or "").strip()
            if end < start:
                end = start + 0.1
            out.append({"start": start, "end": end, "text": text or "..."})
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def normalize_transcript_result(
    result: Any,
    *,
    fallback_path: Optional[str] = None,
    allow_mock_fallback: bool = True,
) -> Dict[str, Any]:
    """
    Normalize provider return to {"language": str, "segments": [...]}.

    Handles accidental non-dict returns and empty segment lists by falling
    back to mock cues when ``allow_mock_fallback`` is True.
    """
    language = "en"
    segments: List[Dict[str, Any]] = []

    if isinstance(result, dict):
        language = str(result.get("language") or "en")
        segments = normalize_segments(result.get("segments"))
    elif isinstance(result, (list, tuple)) and len(result) == 2:
        # Mis-returned (segments, info) tuple from a provider
        segments = normalize_segments(result[0])
        info = result[1]
        language = str(getattr(info, "language", None) or "en")
    elif isinstance(result, (list, tuple)):
        segments = normalize_segments(result)

    if segments or not allow_mock_fallback:
        return {"language": language or "en", "segments": segments}

    duration = 30.0
    if fallback_path:
        try:
            duration = probe_duration(fallback_path) or duration
        except Exception:
            pass
    logger.warning(
        "Captions produced no usable segments; using mock cues (duration=%.1fs)",
        duration,
    )
    return {"language": language or "en", "segments": _mock_segments(duration)}


def transcribe(
    path: str,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Transcribe audio/video path via the captions provider registry.

    Returns {"language": str, "segments": [{"start","end","text"}, ...]}.
    Always normalized; empty provider output falls back to mock cues unless
    AI_FAIL_CLOSED is enabled (then empty segments are returned as-is).
    """
    from src.infrastructure.ai.policy import fail_closed
    from src.infrastructure.ai.registry import get_captions_provider

    raw = get_captions_provider(provider).transcribe(path, model_name=model_name)
    return normalize_transcript_result(
        raw,
        fallback_path=path,
        allow_mock_fallback=not fail_closed(),
    )
