"""Shared OpenAPI error response declarations for /v1 routes."""

from __future__ import annotations

from src.schemas.common import ErrorResponse

# Attached to the v1 APIRouter so Scalar/OpenAPI documents the structured envelope.
ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Bad request"},
    401: {"model": ErrorResponse, "description": "Unauthorized"},
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Not found"},
    409: {"model": ErrorResponse, "description": "Conflict"},
    410: {"model": ErrorResponse, "description": "Gone"},
    413: {"model": ErrorResponse, "description": "Payload too large"},
    422: {"model": ErrorResponse, "description": "Validation failed"},
    429: {"model": ErrorResponse, "description": "Rate limited"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
}
