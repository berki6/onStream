"""No-op email sender."""

from __future__ import annotations

from typing import Optional

from src.infrastructure.email.base import EmailSender


class NoneEmailSender(EmailSender):
    def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        return None
