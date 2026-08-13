"""Video visibility: private | unlisted | public.

``is_public`` stays a derived compatibility flag (True only when public).
Unlisted is tokenless playback but excluded from RSS / catalogs.
"""

from __future__ import annotations

from typing import Optional

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus

PRIVATE = "private"
UNLISTED = "unlisted"
PUBLIC = "public"
ALLOWED = (PRIVATE, UNLISTED, PUBLIC)


def normalize_visibility(
    visibility: Optional[str] = None,
    is_public: Optional[bool] = None,
    current: Optional[str] = None,
) -> str:
    if visibility is not None:
        v = str(visibility).strip().lower()
        if v not in ALLOWED:
            raise AppError(
                "visibility must be private, unlisted, or public",
                code=ErrorCode.VIDEO_BAD_REQUEST,
            )
        return v
    if is_public is True:
        return PUBLIC
    if is_public is False:
        return PRIVATE
    cur = (current or "").strip().lower()
    if cur in ALLOWED:
        return cur
    return PRIVATE


def apply_visibility(
    video: models.Video,
    *,
    visibility: Optional[str] = None,
    is_public: Optional[bool] = None,
) -> str:
    vis = normalize_visibility(
        visibility,
        is_public,
        current=getattr(video, "visibility", None),
    )
    video.visibility = vis
    video.is_public = vis == PUBLIC
    return vis


def effective_visibility(video: models.Video) -> str:
    vis = (getattr(video, "visibility", None) or "").strip().lower()
    if vis in ALLOWED:
        return vis
    return PUBLIC if getattr(video, "is_public", False) else PRIVATE


def allows_tokenless_playback(video: models.Video) -> bool:
    if video.status != VideoStatus.READY:
        return False
    vis = effective_visibility(video)
    if vis in (PUBLIC, UNLISTED):
        return True
    return bool(video.is_public)


def is_rss_listed(video: models.Video) -> bool:
    if video.status != VideoStatus.READY:
        return False
    return effective_visibility(video) == PUBLIC
