"""Storage backend name → constructor registry."""

from __future__ import annotations

from typing import Callable, Dict

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.storage.base import StorageBackend
from src.infrastructure.storage.local import LocalStorage
from src.infrastructure.storage.r2 import R2Storage
from src.infrastructure.storage.s3 import S3Storage, _normalize_addressing_style

logger = get_logger(__name__)

StorageFactory = Callable[[], StorageBackend]


def _build_local() -> StorageBackend:
    return LocalStorage()


def _build_s3() -> StorageBackend:
    endpoint = (settings.S3_ENDPOINT_URL or "").strip() or None
    # AWS defaults to virtual; custom endpoints default to path via S3Storage.
    style = _normalize_addressing_style(
        settings.S3_ADDRESSING_STYLE,
        default="path" if endpoint else "virtual",
    )
    return S3Storage(endpoint_url=endpoint, addressing_style=style)


def _build_minio() -> StorageBackend:
    endpoint = (settings.S3_ENDPOINT_URL or "").strip()
    if not endpoint:
        if settings.ENV == "production":
            raise ValueError(
                "S3_ENDPOINT_URL is required when STORAGE_BACKEND=minio in production"
            )
        endpoint = "http://localhost:9000"
        logger.warning(
            "STORAGE_BACKEND=minio with empty S3_ENDPOINT_URL; using %s", endpoint
        )
    style = _normalize_addressing_style(settings.S3_ADDRESSING_STYLE, default="path")
    return S3Storage(endpoint_url=endpoint, addressing_style=style)


def _build_r2() -> StorageBackend:
    return R2Storage()


STORAGE_REGISTRY: Dict[str, StorageFactory] = {
    "local": _build_local,
    "s3": _build_s3,
    "minio": _build_minio,
    "r2": _build_r2,
}


def create_storage(name: str | None = None) -> StorageBackend:
    """Instantiate a storage backend by registry name."""
    key = (name or settings.STORAGE_BACKEND or "local").lower().strip()
    factory = STORAGE_REGISTRY.get(key)
    if factory is None:
        known = ", ".join(sorted(STORAGE_REGISTRY))
        raise ValueError(f"Unknown STORAGE_BACKEND '{key}'. Expected one of: {known}")
    return factory()


def list_storage_backends() -> list[str]:
    return sorted(STORAGE_REGISTRY.keys())
