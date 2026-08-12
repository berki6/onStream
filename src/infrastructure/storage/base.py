"""Object storage backends for uploads, HLS, and thumbnails."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    @abstractmethod
    def put_file(self, key: str, source: Path) -> None:
        ...

    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> None:
        ...

    @abstractmethod
    def ensure_local(self, key: str) -> Path:
        """Return a local filesystem path for reading (download/cache if needed)."""

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None:
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def health_check(self) -> bool:
        ...

    def put_directory(self, local_dir: Path, key_prefix: str) -> None:
        """Upload all files under local_dir using key_prefix/relative_path."""
        for path in local_dir.rglob("*"):
            if path.is_file():
                rel = path.relative_to(local_dir).as_posix()
                key = f"{key_prefix.rstrip('/')}/{rel}"
                self.put_file(key, path)

    def presign_put(
        self,
        key: str,
        expires_in: int = 3600,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Return a URL the client can PUT to. Local returns API-relative path."""
        raise NotImplementedError

    def append_bytes(self, key: str, data: bytes) -> int:
        """Append bytes to an object (local chunked upload). Returns new size."""
        raise NotImplementedError

    def get_size(self, key: str) -> int:
        raise NotImplementedError
