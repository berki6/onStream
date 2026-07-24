"""Application-layer errors with structured ErrorCode."""

from __future__ import annotations

from typing import Any, List, Optional

from src.application.error_codes import ErrorCode, http_status_for


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: ErrorCode,
        status_code: Optional[int] = None,
        details: Optional[List[dict[str, Any]]] = None,
        headers: Optional[dict[str, str]] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = http_status_for(code, status_code)
        self.details = details
        self.headers = headers
        super().__init__(message)
