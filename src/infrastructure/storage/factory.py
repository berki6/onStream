"""Storage backend factory and re-exports."""

from src.infrastructure.storage.base import StorageBackend
from src.infrastructure.storage.local import LocalStorage
from src.infrastructure.storage.s3 import S3Storage

# Re-export factory symbols; avoid circular import by defining factory in this module
from typing import Optional

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

_storage: Optional[StorageBackend] = None


def get_storage() -> StorageBackend:
    global _storage
    if _storage is None:
        backend = settings.STORAGE_BACKEND.lower()
        if backend == "s3":
            _storage = S3Storage()
            logger.info("Using S3 storage backend")
        else:
            _storage = LocalStorage()
            logger.info("Using local storage backend")
    return _storage


def reset_storage() -> None:
    """Reset cached backend (tests / config reload)."""
    global _storage
    _storage = None
