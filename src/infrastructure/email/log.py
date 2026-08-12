"""Log email sender (development — Laravel-style mail log driver)."""

from __future__ import annotations

from typing import Optional

from src.core.logger import get_logger
from src.infrastructure.email.base import EmailSender

logger = get_logger(__name__)


class LogEmailSender(EmailSender):
    """Write the full message to the application log.

    Intended for local/lab use: set ``EMAIL_PROVIDER=log`` and read the
    password-reset token / deep links from API logs. Production must use
    ``smtp`` (enforced in settings).
    """

    def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        body = body_text or ""
        logger.info(
            "email.sent provider=log to=%s subject=%s\n---\n%s\n---",
            to,
            subject,
            body,
        )
        if body_html:
            logger.debug("email.html_preview length=%s", len(body_html))
