"""Log email sender (development)."""

from __future__ import annotations

from typing import Optional

from src.core.logger import get_logger
from src.infrastructure.email.base import EmailSender

logger = get_logger(__name__)


class LogEmailSender(EmailSender):
    def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        body = body_text or ""
        # Avoid dumping reset JWTs / secrets into durable logs.
        if "password reset" in (subject or "").lower() or "eyJ" in body:
            preview = f"[redacted length={len(body)}]"
        else:
            preview = body[:200]
        logger.info(
            "Email to=%s subject=%s body=%s",
            to,
            subject,
            preview,
        )
