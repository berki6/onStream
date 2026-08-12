"""Object storage backends."""

from src.infrastructure.storage.base import StorageBackend
from src.infrastructure.storage.factory import get_storage, reset_storage
from src.infrastructure.storage.local import LocalStorage
from src.infrastructure.storage.r2 import R2Storage
from src.infrastructure.storage.registry import create_storage, list_storage_backends
from src.infrastructure.storage.s3 import S3Storage

__all__ = [
    "StorageBackend",
    "LocalStorage",
    "S3Storage",
    "R2Storage",
    "get_storage",
    "reset_storage",
    "create_storage",
    "list_storage_backends",
]
