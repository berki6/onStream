"""Shared helpers for public video IDs.

Path params are named ``video_id`` but the value is the public ``upload_id``
(8-char alphanumeric). The DB column remains ``upload_id``.
"""

from __future__ import annotations

import string

from src.application.error_codes import ErrorCode
from src.application.errors import AppError


def validate_public_video_id(video_id: str) -> str:
    """Validate public video id (upload_id). Raises AppError on invalid format."""
    if not video_id or len(video_id) != 8:
        raise AppError("Invalid upload ID format", code=ErrorCode.VALIDATION_INVALID_ID)
    safe_chars = "".join(
        c for c in (string.ascii_letters + string.digits) if c not in "0O1Il"
    )
    if not all(c in safe_chars for c in video_id):
        raise AppError("Invalid upload ID format", code=ErrorCode.VALIDATION_INVALID_ID)
    return video_id
