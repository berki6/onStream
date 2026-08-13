"""API key scope catalog and path → scope mapping.

JWT sessions are unrestricted. Machine keys must opt into each scope;
the default (`upload,read,webhooks`) is least-privilege, not god-mode.
"""

from __future__ import annotations

from typing import FrozenSet, Optional

from src.application.error_codes import ErrorCode
from src.application.errors import AppError

ALLOWED_SCOPES: FrozenSet[str] = frozenset({"read", "upload", "write", "webhooks"})
DEFAULT_SCOPES = "upload,read,webhooks"
JWT_ONLY = "jwt"
LAST_USED_MIN_INTERVAL_SECONDS = 60


def parse_scopes(raw: Optional[str], *, default: str = DEFAULT_SCOPES) -> FrozenSet[str]:
    text = (raw if raw is not None else default) or ""
    parts = {p.strip().lower() for p in text.split(",") if p.strip()}
    if not parts:
        raise AppError(
            "API key needs at least one scope",
            code=ErrorCode.API_KEY_BAD_REQUEST,
        )
    unknown = parts - ALLOWED_SCOPES
    if unknown:
        raise AppError(
            f"Unknown API key scope(s): {', '.join(sorted(unknown))}",
            code=ErrorCode.API_KEY_BAD_REQUEST,
        )
    return frozenset(parts)


def serialize_scopes(scopes: FrozenSet[str]) -> str:
    return ",".join(sorted(scopes))


def _norm_path(path: str) -> str:
    p = (path or "").split("?", 1)[0]
    if len(p) > 1:
        p = p.rstrip("/")
    return p


def required_scope(method: str, path: str) -> str:
    """Return a catalog scope, or JWT_ONLY if machine keys are forbidden."""
    method = (method or "GET").upper()
    path = _norm_path(path)
    mutate = method not in {"GET", "HEAD", "OPTIONS"}

    if path.startswith("/v1/api-keys") or path.startswith("/v1/auth"):
        return JWT_ONLY
    if path.startswith("/v1/moderation"):
        return "write"
    if path.startswith("/v1/webhooks"):
        return "webhooks"
    if path.startswith("/v1/uploads"):
        return "upload"
    if path == "/v1/videos" and method == "POST":
        return "upload"
    if path.endswith("/tokens") and method == "POST":
        return "read"
    if mutate:
        return "write"
    return "read"


def assert_api_key_allowed(scopes_raw: Optional[str], method: str, path: str) -> None:
    need = required_scope(method, path)
    if need == JWT_ONLY:
        raise AppError(
            "API keys cannot call this route; sign in with a user session",
            code=ErrorCode.API_KEY_FORBIDDEN,
        )
    try:
        granted = parse_scopes(scopes_raw)
    except AppError:
        raise AppError(
            "API key scopes are invalid",
            code=ErrorCode.API_KEY_FORBIDDEN,
        )
    if need not in granted:
        raise AppError(
            f"API key is missing the '{need}' scope",
            code=ErrorCode.API_KEY_FORBIDDEN,
        )
