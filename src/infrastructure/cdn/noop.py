"""No-op CDN purger (default)."""

from __future__ import annotations

from typing import Sequence

from src.core.logger import get_logger
from src.infrastructure.cdn.base import CdnPurger

logger = get_logger(__name__)


class NoopCdnPurger(CdnPurger):
    def purge_urls(self, urls: Sequence[str]) -> None:
        if urls:
            logger.debug("CDN purge noop: %s", list(urls))
