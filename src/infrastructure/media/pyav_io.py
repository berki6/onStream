"""PyAV-backed media I/O helpers (probe, audio extract, frame sampling)."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from src.core.logger import get_logger

logger = get_logger(__name__)


def _open_container(path: str):
    import av

    return av.open(path)


def probe_duration(video_path: str) -> float:
    """Return media duration in seconds, or 0.0 on failure."""
    try:
        with _open_container(video_path) as container:
            if container.duration is not None:
                return float(container.duration) / av_time_base()
            # Fallback: max stream duration
            best = 0.0
            for stream in container.streams:
                if stream.duration is not None and stream.time_base is not None:
                    best = max(best, float(stream.duration * stream.time_base))
            return best
    except Exception as exc:
        logger.debug("PyAV probe_duration failed for %s: %s", video_path, exc)
        return 0.0


def av_time_base() -> float:
    """AV_TIME_BASE as float (1e6)."""
    try:
        import av

        return float(av.time_base)
    except Exception:
        return 1_000_000.0


def probe_height(video_path: str) -> int:
    """Return first video stream height, or 720 on failure."""
    try:
        with _open_container(video_path) as container:
            for stream in container.streams.video:
                h = stream.height
                if h:
                    return int(h)
    except Exception as exc:
        logger.debug("PyAV probe_height failed for %s: %s", video_path, exc)
    return 720


def extract_audio_pcm_or_wav(
    video_path: str,
    audio_path: str,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
) -> str:
    """
    Extract mono WAV audio via PyAV. Returns ``audio_path``.

    Raises on failure so callers can fall back to ffmpeg shell.
    """
    import av
    import wave

    out = Path(audio_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with av.open(video_path) as container:
        audio_streams = list(container.streams.audio)
        if not audio_streams:
            raise RuntimeError("No audio stream")
        stream = audio_streams[0]
        resampler = av.audio.resampler.AudioResampler(
            format="s16",
            layout="mono" if channels == 1 else "stereo",
            rate=sample_rate,
        )
        frames_data = bytearray()
        for packet in container.demux(stream):
            for frame in packet.decode():
                for resampled in resampler.resample(frame):
                    frames_data.extend(bytes(resampled.planes[0]))
        # Flush resampler
        for resampled in resampler.resample(None):
            frames_data.extend(bytes(resampled.planes[0]))

    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # s16
        wf.setframerate(sample_rate)
        wf.writeframes(frames_data)

    return str(out)


def sample_frames(
    video_path: str,
    sample_count: int = 5,
    *,
    width: int = 64,
    height: int = 36,
    gray: bool = True,
) -> List:
    """
    Sample up to ``sample_count`` frames as numpy arrays.

    Returns a list of ndarray (H, W) if gray else (H, W, 3). Empty on failure.
    """
    try:
        import av
        import numpy as np
    except ImportError as exc:
        logger.debug("PyAV/numpy unavailable for sample_frames: %s", exc)
        return []

    path = Path(video_path)
    if not path.exists():
        return []

    frames: List = []
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            duration = probe_duration(str(path)) or 10.0
            targets = [
                (duration * (i + 1)) / (sample_count + 1) for i in range(sample_count)
            ]
            # Seek-based sampling
            for t in targets:
                try:
                    container.seek(int(t / float(stream.time_base)), stream=stream)
                except Exception:
                    pass
                for frame in container.decode(stream):
                    img = frame.to_ndarray(format="gray" if gray else "rgb24")
                    # Simple nearest resize via slicing / repeat if needed
                    if img.shape[0] != height or img.shape[1] != width:
                        try:
                            import cv2

                            img = cv2.resize(img, (width, height))
                        except Exception:
                            # Crude downsample
                            ys = max(1, img.shape[0] // height)
                            xs = max(1, img.shape[1] // width)
                            img = img[::ys, ::xs][:height, :width]
                            if img.shape[0] < height or img.shape[1] < width:
                                pad = np.zeros(
                                    (height, width) if gray else (height, width, 3),
                                    dtype=img.dtype,
                                )
                                pad[: img.shape[0], : img.shape[1]] = img[
                                    :height, :width
                                ]
                                img = pad
                    frames.append(img)
                    break
                if len(frames) >= sample_count:
                    break
    except Exception as exc:
        logger.debug("PyAV sample_frames failed for %s: %s", video_path, exc)
        return frames

    return frames


def frame_laplacian_variance(frame) -> float:
    """Variance of Laplacian (focus/contrast proxy). Requires OpenCV."""
    try:
        import cv2
        import numpy as np

        arr = np.asarray(frame, dtype=np.float64)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr.astype("uint8"), cv2.COLOR_RGB2GRAY).astype(
                np.float64
            )
        lap = cv2.Laplacian(arr.astype("uint8"), cv2.CV_64F)
        return float(lap.var())
    except Exception:
        try:
            import numpy as np

            arr = np.asarray(frame, dtype=np.float64).ravel()
            if arr.size == 0:
                return 0.0
            mean = float(arr.mean())
            return float(((arr - mean) ** 2).mean())
        except Exception:
            return 0.0
