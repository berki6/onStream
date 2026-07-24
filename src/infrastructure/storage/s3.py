"""S3-compatible object storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.storage.base import StorageBackend
from src.utils.paths import PROJECT_ROOT, ensure_dir

logger = get_logger(__name__)


class S3Storage(StorageBackend):
    def __init__(self) -> None:
        import boto3
        from botocore.client import Config

        self.bucket = settings.S3_BUCKET
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        self._cache_dir = PROJECT_ROOT / "data" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _object_key(self, key: str) -> str:
        return key.replace("\\", "/").lstrip("/")

    def put_file(self, key: str, source: Path) -> None:
        self._client.upload_file(str(source), self.bucket, self._object_key(key))

    def put_bytes(self, key: str, data: bytes) -> None:
        self._client.put_object(
            Bucket=self.bucket, Key=self._object_key(key), Body=data
        )

    def ensure_local(self, key: str) -> Path:
        dest = self._cache_dir / self._object_key(key)
        ensure_dir(dest)
        if not dest.exists():
            self._client.download_file(self.bucket, self._object_key(key), str(dest))
        return dest

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=self._object_key(key))
        except Exception as e:
            logger.warning(f"S3 delete failed for {key}: {e}")
        cached = self._cache_dir / self._object_key(key)
        if cached.exists():
            cached.unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        prefix_key = self._object_key(prefix)
        if not prefix_key.endswith("/"):
            prefix_key += "/"
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix_key):
            contents = page.get("Contents") or []
            if not contents:
                continue
            self._client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
            )
        cache_prefix = self._cache_dir / prefix_key.rstrip("/")
        if cache_prefix.exists():
            shutil.rmtree(cache_prefix, ignore_errors=True)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._object_key(key))
            return True
        except Exception:
            return False

    def health_check(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self.bucket)
            return True
        except Exception as e:
            logger.error(f"S3 storage health check failed: {e}")
            return False

    def presign_put(
        self,
        key: str,
        expires_in: int = 3600,
        content_type: str = "application/octet-stream",
    ) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": self._object_key(key),
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )

    def append_bytes(self, key: str, data: bytes) -> int:
        # S3 does not support true append; download-merge-upload for small chunks
        obj_key = self._object_key(key)
        existing = b""
        try:
            resp = self._client.get_object(Bucket=self.bucket, Key=obj_key)
            existing = resp["Body"].read()
        except Exception:
            pass
        merged = existing + data
        self._client.put_object(Bucket=self.bucket, Key=obj_key, Body=merged)
        return len(merged)

    def get_size(self, key: str) -> int:
        try:
            resp = self._client.head_object(
                Bucket=self.bucket, Key=self._object_key(key)
            )
            return int(resp.get("ContentLength", 0))
        except Exception:
            return 0
