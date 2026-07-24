"""Email sender protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class EmailSender(ABC):
    @abstractmethod
    def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        ...
