"""Tokenized playback asset URLs for storyboard / captions."""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote

from src.core.config import settings
from src.infrastructure.db import models


def _q(token: Optional[str]) -> str:
    if not token:
        return ""
    return f"?token={quote(token)}"


def playback_media_urls(
    video: models.Video, token: Optional[str] = None
) -> Dict[str, Any]:
    base = settings.PUBLIC_API_BASE_URL.rstrip("/")
    uid = video.upload_id
    q = _q(token)
    out: Dict[str, Any] = {}
    if video.storyboard_path:
        out["storyboard_url"] = f"{base}/v1/playback/{uid}/storyboard.jpg{q}"
    if video.storyboard_vtt_path:
        out["storyboard_vtt_url"] = f"{base}/v1/playback/{uid}/storyboard.vtt{q}"
    if video.caption_vtt_path:
        out["captions_url"] = f"{base}/v1/playback/{uid}/captions.vtt{q}"
    return out


def video_payload(video: models.Video, token: Optional[str] = None) -> Dict[str, Any]:
    from src.application.visibility import effective_visibility
    from src.schemas.video import Video

    data = Video.model_validate(video).model_dump()
    data["visibility"] = effective_visibility(video)
    data.update(playback_media_urls(video, token=token))
    return data
