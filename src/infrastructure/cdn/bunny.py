"""Bunny.net URL purge API."""

from __future__ import annotations

from typing import Sequence
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.cdn.base import CdnPurger

logger = get_logger(__name__)


class BunnyCdnPurger(CdnPurger):
    def __init__(
        self,
        *,
        api_key: str | None = None,
        pull_zone_id: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.BUNNY_API_KEY
        self.pull_zone_id = pull_zone_id or settings.BUNNY_PULL_ZONE_ID

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=8))
    def _purge_one(self, target_url: str) -> None:
        if not self.api_key:
            logger.warning("Bunny purge skipped: missing API key")
            return
        # Bunny purge URL endpoint
        api = (
            "https://api.bunny.net/purge"
            f"?url={quote(target_url, safe='')}"
        )
        headers = {
            "AccessKey": self.api_key,
            "Accept": "application/json",
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(api, headers=headers)
            resp.raise_for_status()

    def purge_urls(self, urls: Sequence[str]) -> None:
        cleaned = [u for u in urls if u]
        if not cleaned:
            return
        try:
            for u in cleaned:
                self._purge_one(u)
            logger.info("Bunny purged %d URL(s)", len(cleaned))
        except Exception as exc:
            logger.warning("Bunny purge error: %s", exc)
            raise
