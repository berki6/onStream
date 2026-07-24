"""CDN cache purge backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence


class CdnPurger(ABC):
    @abstractmethod
    def purge_urls(self, urls: Sequence[str]) -> None:
        """Purge the given absolute URLs from the CDN edge cache."""
