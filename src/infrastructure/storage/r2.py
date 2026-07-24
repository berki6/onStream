"""Cloudflare R2 object storage (S3-compatible profile)."""

from __future__ import annotations

from urllib.parse import urlparse

from src.core.config import settings
from src.infrastructure.storage.s3 import S3Storage, _normalize_addressing_style


class R2Storage(S3Storage):
    """
    R2 uses the S3 API with a required account endpoint and region ``auto``.

    Per Cloudflare docs: ``region_name='auto'``, endpoint
    ``https://<account_id>.r2.cloudflarestorage.com``. Path-style is the
    safer default for S3-compatible clients.
    """

    def __init__(self) -> None:
        endpoint = (settings.S3_ENDPOINT_URL or "").strip()
        if not endpoint:
            raise ValueError(
                "S3_ENDPOINT_URL is required when STORAGE_BACKEND=r2 "
                "(e.g. https://<account_id>.r2.cloudflarestorage.com)"
            )
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(
                f"S3_ENDPOINT_URL must be an absolute http(s) URL, got: {endpoint!r}"
            )
        if "r2.cloudflarestorage.com" not in parsed.netloc.lower():
            # Allow custom CNAME endpoints but require https in production.
            if settings.ENV == "production" and parsed.scheme != "https":
                raise ValueError(
                    "S3_ENDPOINT_URL for R2 must use https in production"
                )

        style = _normalize_addressing_style(
            settings.S3_ADDRESSING_STYLE, default="path"
        )
        # Cloudflare R2 SigV4 expects region "auto" (us-east-1 aliases, but
        # prefer the documented value so operators match official examples).
        configured = (settings.S3_REGION or "").strip().lower()
        region = "auto" if configured in {"", "auto", "us-east-1"} else configured

        super().__init__(
            endpoint_url=endpoint,
            region_name=region,
            addressing_style=style,
        )
