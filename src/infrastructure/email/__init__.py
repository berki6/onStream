"""Outbound email providers."""

from src.infrastructure.email.base import EmailSender
from src.infrastructure.email.registry import (
    create_email_sender,
    get_email_sender,
    reset_email_sender,
)

__all__ = [
    "EmailSender",
    "get_email_sender",
    "create_email_sender",
    "reset_email_sender",
]
