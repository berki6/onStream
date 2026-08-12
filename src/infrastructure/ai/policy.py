"""Shared AI provider policy helpers."""

from __future__ import annotations

from src.core.config import settings


def fail_closed() -> bool:
    """Production must not silently substitute mock providers."""
    return settings.ENV == "production"
