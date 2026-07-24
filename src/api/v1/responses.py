"""Thin helpers for mapping AppError → HTTP and building APIResponse."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Request

from src.application.errors import AppError
from src.schemas.common import APIResponse, PaginatedResponse


def raise_app_error(exc: AppError) -> None:
    """Re-raise AppError so the global structured error handler formats it."""
    raise exc


def api_ok(request: Request, data, message: str | None = None) -> APIResponse:
    return APIResponse(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        timestamp=datetime.now(timezone.utc),
        message=message,
    )


def api_page(
    request: Request,
    data,
    *,
    total_count: int,
    skip: int,
    limit: int,
    message: str | None = None,
) -> PaginatedResponse:
    return PaginatedResponse(
        data=data,
        request_id=getattr(request.state, "request_id", "unknown"),
        timestamp=datetime.now(timezone.utc),
        message=message,
        pagination={
            "total_count": total_count,
            "page": (skip // limit) + 1 if limit else 1,
            "per_page": limit,
            "has_more": skip + limit < total_count,
        },
    )
