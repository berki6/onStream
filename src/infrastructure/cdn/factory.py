"""CDN purger factory."""

from __future__ import annotations

from typing import Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.cdn.base import CdnPurger
from src.infrastructure.cdn.bunny import BunnyCdnPurger
from src.infrastructure.cdn.cloudflare import CloudflareCdnPurger
from src.infrastructure.cdn.noop import NoopCdnPurger

logger = get_logger(__name__)

_purger: Optional[CdnPurger] = None


def get_cdn_purger() -> CdnPurger:
    global _purger
    if _purger is None:
        provider = (settings.CDN_PROVIDER or "none").lower().strip()
        if provider == "cloudflare":
            _purger = CloudflareCdnPurger()
            logger.info("Using Cloudflare CDN purger")
        elif provider == "bunny":
            _purger = BunnyCdnPurger()
            logger.info("Using Bunny CDN purger")
        else:
            _purger = NoopCdnPurger()
            logger.info("Using noop CDN purger")
    return _purger


def reset_cdn_purger() -> None:
    """Reset cached purger (tests / config reload)."""
    global _purger
    _purger = None
