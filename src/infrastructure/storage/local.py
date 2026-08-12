"""Local filesystem storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.storage.base import StorageBackend
from src.utils.paths import ensure_dir, to_absolute_path

logger = get_logger(__name__)


class LocalStorage(StorageBackend):
    def put_file(self, key: str, source: Path) -> None:
        dest = to_absolute_path(key)
        ensure_dir(dest)
        if source.resolve() != dest.resolve():
            shutil.copy2(source, dest)

    def put_bytes(self, key: str, data: bytes) -> None:
        dest = to_absolute_path(key)
        ensure_dir(dest)
        dest.write_bytes(data)

    def ensure_local(self, key: str) -> Path:
        path = to_absolute_path(key)
        if not path.exists():
            raise FileNotFoundError(f"Local object not found: {key}")
        return path

    def delete(self, key: str) -> None:
        path = to_absolute_path(key)
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)

    def delete_prefix(self, prefix: str) -> None:
        path = to_absolute_path(prefix)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            path.unlink(missing_ok=True)

    def exists(self, key: str) -> bool:
        return to_absolute_path(key).exists()

    def health_check(self) -> bool:
        try:
            settings.VIDEO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            probe = settings.VIDEO_UPLOAD_DIR / ".health"
            probe.write_text("ok")
            probe.unlink(missing_ok=True)
            return True
        except OSError as e:
            logger.error(f"Local storage health check failed: {e}")
            return False

    def presign_put(
        self,
        key: str,
        expires_in: int = 3600,
        content_type: str = "application/octet-stream",
    ) -> str:
        # Client uploads via API: PUT /v1/uploads/{session}/content
        return f"{settings.PUBLIC_API_BASE_URL}/v1/uploads/by-key/{key}"

    def append_bytes(self, key: str, data: bytes) -> int:
        dest = to_absolute_path(key)
        ensure_dir(dest)
        with open(dest, "ab") as f:
            f.write(data)
        return dest.stat().st_size

    def get_size(self, key: str) -> int:
        path = to_absolute_path(key)
        if not path.exists():
            return 0
        return path.stat().st_size
