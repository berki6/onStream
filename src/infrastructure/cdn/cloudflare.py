"""Cloudflare cache purge via zones API."""

from __future__ import annotations

from typing import Sequence

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.cdn.base import CdnPurger

logger = get_logger(__name__)


class CloudflareCdnPurger(CdnPurger):
    def __init__(
        self,
        *,
        api_token: str | None = None,
        zone_id: str | None = None,
    ) -> None:
        self.api_token = api_token or settings.CLOUDFLARE_API_TOKEN
        self.zone_id = zone_id or settings.CLOUDFLARE_ZONE_ID

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    def _post(self, urls: list[str]) -> None:
        if not self.api_token or not self.zone_id:
            logger.warning("Cloudflare purge skipped: missing token or zone_id")
            return
        url = f"https://api.cloudflare.com/client/v4/zones/{self.zone_id}/purge_cache"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(url, headers=headers, json={"files": urls})
            resp.raise_for_status()
            body = resp.json()
            if not body.get("success", True):
                raise RuntimeError(f"Cloudflare purge failed: {body}")

    def purge_urls(self, urls: Sequence[str]) -> None:
        cleaned = [u for u in urls if u]
        if not cleaned:
            return
        try:
            self._post(cleaned)
            logger.info("Cloudflare purged %d URL(s)", len(cleaned))
        except Exception as exc:
            logger.warning("Cloudflare purge error: %s", exc)
            raise
