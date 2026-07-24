"""Error envelope builders shared by exception handlers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Optional, Union

from fastapi import Request

from src.application.error_codes import ErrorCode


def error_body(
    *,
    request: Optional[Request],
    code: Union[ErrorCode, str],
    message: str,
    details: Optional[List[dict[str, Any]]] = None,
) -> dict[str, Any]:
    code_value = code.value if isinstance(code, ErrorCode) else str(code)
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
