"""SMTP email sender."""

from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from src.core.config import settings
from src.infrastructure.email.base import EmailSender


def validate_smtp_settings() -> None:
    host = (settings.SMTP_HOST or "").strip()
    if not host:
        raise ValueError("SMTP_HOST is required when EMAIL_PROVIDER=smtp")
    if not (1 <= int(settings.SMTP_PORT) <= 65535):
        raise ValueError("SMTP_PORT must be between 1 and 65535")
    if not (settings.SMTP_FROM or "").strip():
        raise ValueError("SMTP_FROM is required when EMAIL_PROVIDER=smtp")
    user = (settings.SMTP_USER or "").strip()
    if user and not (settings.SMTP_PASSWORD or "").strip():
        raise ValueError("SMTP_PASSWORD is required when SMTP_USER is set")


class SmtpEmailSender(EmailSender):
    def __init__(self) -> None:
        validate_smtp_settings()

    def send(
        self,
        to: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> None:
        validate_smtp_settings()
        host = (settings.SMTP_HOST or "").strip()
        to_addr = (to or "").strip()
        if not to_addr or "@" not in to_addr:
            raise ValueError(f"Invalid recipient address: {to!r}")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to_addr
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP(host, settings.SMTP_PORT, timeout=30) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            user = (settings.SMTP_USER or "").strip()
            if user:
                server.login(user, settings.SMTP_PASSWORD or "")
            server.sendmail(settings.SMTP_FROM, [to_addr], msg.as_string())
