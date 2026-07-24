"""S3-compatible object storage backend."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from botocore.exceptions import ClientError

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.storage.base import StorageBackend
from src.utils.paths import PROJECT_ROOT, ensure_dir

logger = get_logger(__name__)


def _normalize_addressing_style(style: Optional[str], *, default: str) -> str:
    value = (style or "").strip().lower() or default
    if value not in {"path", "virtual"}:
        raise ValueError(
            f"Invalid S3 addressing style '{style}'. Expected 'path' or 'virtual'."
        )
    return value


def _is_missing_key_error(exc: BaseException) -> bool:
    if not isinstance(exc, ClientError):
        return False
    code = (exc.response or {}).get("Error", {}).get("Code", "")
    return code in {"404", "NoSuchKey", "NotFound", "NoSuchBucket"}


class S3Storage(StorageBackend):
    """Generic S3 API client (AWS, MinIO, R2, and other compatible endpoints)."""

    def __init__(
        self,
        *,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        addressing_style: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket: Optional[str] = None,
    ) -> None:
        import boto3
        from botocore.client import Config

        self.bucket = (bucket if bucket is not None else settings.S3_BUCKET or "").strip()
        if not self.bucket:
            raise ValueError("S3_BUCKET is required for S3-compatible storage")

        if endpoint_url is not None:
            endpoint = (endpoint_url or "").strip() or None
        else:
            endpoint = (settings.S3_ENDPOINT_URL or "").strip() or None

        region = region_name if region_name is not None else settings.S3_REGION
        # Custom endpoints (MinIO/R2/etc.) are safer with path-style when unset.
        default_style = "path" if endpoint else "virtual"
        style = _normalize_addressing_style(
            addressing_style
            if addressing_style is not None
            else settings.S3_ADDRESSING_STYLE,
            default=default_style,
        )

        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=(
                access_key if access_key is not None else settings.S3_ACCESS_KEY
            ),
            aws_secret_access_key=(
                secret_key if secret_key is not None else settings.S3_SECRET_KEY
            ),
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": style},
            ),
        )
        self._cache_dir = PROJECT_ROOT / "data" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _object_key(self, key: str) -> str:
        normalized = key.replace("\\", "/").lstrip("/")
        parts = [p for p in normalized.split("/") if p not in ("", ".")]
        if any(p == ".." for p in parts):
            raise ValueError(f"Unsafe object key (path traversal): {key!r}")
        return "/".join(parts)

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
        obj_key = self._object_key(key)
        try:
            self._client.delete_object(Bucket=self.bucket, Key=obj_key)
        except Exception as e:
            logger.error("S3 delete failed for %s: %s", key, e)
            raise
        cached = self._cache_dir / obj_key
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
            resp = self._client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in contents]},
            )
            errors = resp.get("Errors") or []
            if errors:
                sample = errors[0]
                raise RuntimeError(
                    f"S3 delete_prefix partial failure under {prefix_key}: "
                    f"{sample.get('Key')} {sample.get('Code')} {sample.get('Message')}"
                )
        cache_prefix = self._cache_dir / prefix_key.rstrip("/")
        if cache_prefix.exists():
            shutil.rmtree(cache_prefix, ignore_errors=True)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=self._object_key(key))
            return True
        except ClientError as e:
            if _is_missing_key_error(e):
                return False
            logger.error("S3 exists check failed for %s: %s", key, e)
            raise
        except Exception as e:
            logger.error("S3 exists check failed for %s: %s", key, e)
            raise

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
        except ClientError as e:
            if not _is_missing_key_error(e):
                logger.error("S3 append read failed for %s: %s", key, e)
                raise
        except Exception as e:
            logger.error("S3 append read failed for %s: %s", key, e)
            raise
        merged = existing + data
        self._client.put_object(Bucket=self.bucket, Key=obj_key, Body=merged)
        return len(merged)

    def get_size(self, key: str) -> int:
        try:
            resp = self._client.head_object(
                Bucket=self.bucket, Key=self._object_key(key)
            )
            return int(resp.get("ContentLength", 0))
        except ClientError as e:
            if _is_missing_key_error(e):
                return 0
            logger.error("S3 get_size failed for %s: %s", key, e)
            raise
        except Exception as e:
            logger.error("S3 get_size failed for %s: %s", key, e)
            raise
