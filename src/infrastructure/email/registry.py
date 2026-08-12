"""Email provider registry."""

from __future__ import annotations

from typing import Callable, Dict, Optional

from src.core.config import settings
from src.infrastructure.email.base import EmailSender
from src.infrastructure.email.log import LogEmailSender
from src.infrastructure.email.none import NoneEmailSender
from src.infrastructure.email.smtp import SmtpEmailSender

EmailFactory = Callable[[], EmailSender]

EMAIL_REGISTRY: Dict[str, EmailFactory] = {
    "none": NoneEmailSender,
    "log": LogEmailSender,
    "smtp": SmtpEmailSender,
}

_sender: Optional[EmailSender] = None


def create_email_sender(name: Optional[str] = None) -> EmailSender:
    key = (name or settings.EMAIL_PROVIDER or "log").lower().strip()
    factory = EMAIL_REGISTRY.get(key)
    if factory is None:
        known = ", ".join(sorted(EMAIL_REGISTRY))
        raise ValueError(f"Unknown EMAIL_PROVIDER '{key}'. Expected: {known}")
    return factory()


def get_email_sender() -> EmailSender:
    global _sender
    if _sender is None:
        _sender = create_email_sender()
    return _sender


def reset_email_sender() -> None:
    global _sender
    _sender = None
