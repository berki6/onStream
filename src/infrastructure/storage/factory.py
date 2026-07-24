"""Storage backend factory and re-exports."""

from __future__ import annotations

from typing import Optional

from src.core.logger import get_logger
from src.infrastructure.storage.base import StorageBackend
from src.infrastructure.storage.registry import create_storage

logger = get_logger(__name__)

_storage: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        _storage = create_storage()
        logger.info("Using storage backend: %s", type(_storage).__name__)
    return _storage


def reset_storage() -> None:
    """Reset cached backend (tests / config reload)."""
    global _storage
    _storage = None
