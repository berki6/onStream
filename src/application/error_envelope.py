"""Error envelope builders shared by exception handlers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional, Union

from fastapi import Request

from src.application.error_codes import ErrorCode


def record_api_error(code: Union[ErrorCode, str], http_status: int) -> None:
    """Increment Prometheus error counter (best-effort)."""
    try:
        from src.core.metrics import API_ERRORS

        code_value = code.value if isinstance(code, ErrorCode) else str(code)
        API_ERRORS.labels(code=code_value, http_status=str(http_status)).inc()
    except Exception:
        pass


def validation_detail_code(field: str, err_type: str) -> ErrorCode:
    """Pick a more specific code for common validation shapes."""
    field_l = (field or "").lower()
    type_l = (err_type or "").lower()
    id_fields = {
        "upload_id",
        "stream_id",
        "video_id",
        "session_id",
        "playlist_id",
    }
    if field_l in id_fields or field_l.endswith("_id"):
        if any(
            token in type_l
            for token in (
                "pattern",
                "string_too_short",
                "string_too_long",
                "value_error",
            )
        ):
            return ErrorCode.VALIDATION_INVALID_ID
    return ErrorCode.VALIDATION_FAILED


def error_body(
    *,
    request: Optional[Request],
    code: Union[ErrorCode, str],
    message: str,
    details: Optional[List[dict[str, Any]]] = None,
    http_status: Optional[int] = None,
) -> dict[str, Any]:
    code_value = code.value if isinstance(code, ErrorCode) else str(code)
    if http_status is not None:
        record_api_error(code, http_status)
    request_id = "unknown"
    if request is not None:
        request_id = getattr(request.state, "request_id", None) or request.headers.get(
            "X-Request-ID", "unknown"
        )
    return {
        "success": False,
        "error": {
            "code": code_value,
            "message": message,
            "details": details,
        },
        "request_id": request_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_version": "v1",
    }
