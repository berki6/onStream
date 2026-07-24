"""Email provider registry and password-reset wiring tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.application import auth_service
from src.infrastructure.email.log import LogEmailSender
from src.infrastructure.email.none import NoneEmailSender
from src.infrastructure.email.registry import (
    create_email_sender,
    get_email_sender,
    reset_email_sender,
)
from src.infrastructure.email.smtp import SmtpEmailSender


@pytest.fixture(autouse=True)
def _reset_email():
    reset_email_sender()
    yield
    reset_email_sender()


def test_create_none_sender():
    assert isinstance(create_email_sender("none"), NoneEmailSender)


def test_create_log_sender():
    assert isinstance(create_email_sender("log"), LogEmailSender)


def test_create_smtp_sender(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_HOST", "smtp.example.com"
    )
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_FROM", "noreply@test"
    )
    assert isinstance(create_email_sender("smtp"), SmtpEmailSender)


def test_unknown_email_provider():
    with pytest.raises(ValueError, match="Unknown EMAIL_PROVIDER"):
        create_email_sender("sendgrid")


def test_none_send_is_noop():
    create_email_sender("none").send("a@b.c", "Sub", "Body")


def test_log_send_emits(caplog):
    with caplog.at_level("INFO"):
        create_email_sender("log").send("user@example.com", "Hello", "World body")
    assert any("user@example.com" in r.message for r in caplog.records)


def test_smtp_send_uses_smtplib(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_HOST", "smtp.example.com"
    )
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_PORT", 587
    )
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_FROM", "noreply@test"
    )
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_USER", "u"
    )
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_PASSWORD", "p"
    )
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_USE_TLS", True
    )

    mock_smtp = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_smtp
    mock_ctx.__exit__.return_value = False

    with patch("src.infrastructure.email.smtp.smtplib.SMTP", return_value=mock_ctx):
        create_email_sender("smtp").send("to@x.com", "Subj", "plain", body_html="<p>x</p>")

    mock_smtp.starttls.assert_called_once()
    mock_smtp.login.assert_called_once_with("u", "p")
    mock_smtp.sendmail.assert_called_once()
    args = mock_smtp.sendmail.call_args[0]
    assert args[0] == "noreply@test"
    assert args[1] == ["to@x.com"]


def test_password_reset_sends_when_user_exists(db_session, test_user, monkeypatch):
    sender = MagicMock()
    monkeypatch.setattr(
        "src.infrastructure.email.registry.get_email_sender",
        lambda: sender,
    )
    # auth_service imports get_email_sender inside the function
    with patch(
        "src.infrastructure.email.get_email_sender",
        return_value=sender,
    ):
        data = auth_service.request_password_reset(db_session, test_user.email)

    assert data["requested"] is True
    sender.send.assert_called_once()
    kwargs = sender.send.call_args.kwargs
    assert kwargs["to"] == test_user.email
    assert "password reset" in kwargs["subject"].lower()
    assert "reset_token" in data  # non-prod includes token


def test_password_reset_never_returns_token_in_production(
    db_session, test_user, monkeypatch
):
    sender = MagicMock()
    monkeypatch.setattr(
        "src.application.auth_service.settings.ENV", "production"
    )
    monkeypatch.setattr(
        "src.application.auth_service.settings.DEBUG", True
    )
    with patch(
        "src.infrastructure.email.get_email_sender",
        return_value=sender,
    ):
        data = auth_service.request_password_reset(db_session, test_user.email)
    assert data["requested"] is True
    assert "reset_token" not in data
    sender.send.assert_called_once()


def test_password_reset_logs_send_failure(db_session, test_user, caplog):
    sender = MagicMock()
    sender.send.side_effect = RuntimeError("smtp down")
    with patch(
        "src.infrastructure.email.get_email_sender",
        return_value=sender,
    ):
        with caplog.at_level("ERROR"):
            data = auth_service.request_password_reset(db_session, test_user.email)
    assert data["requested"] is True
    assert any("password_reset_email_failed" in r.message for r in caplog.records)


def test_smtp_create_requires_host(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.email.smtp.settings.SMTP_HOST", ""
    )
    with pytest.raises(ValueError, match="SMTP_HOST"):
        create_email_sender("smtp")


def test_password_reset_no_send_when_unknown_email(db_session, monkeypatch):
    sender = MagicMock()
    with patch(
        "src.infrastructure.email.get_email_sender",
        return_value=sender,
    ):
        data = auth_service.request_password_reset(
            db_session, "nobody-exists@example.com"
        )

    assert data["requested"] is True
    sender.send.assert_not_called()


def test_get_email_sender_singleton(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.email.registry.settings.EMAIL_PROVIDER", "none"
    )
    reset_email_sender()
    a = get_email_sender()
    b = get_email_sender()
    assert a is b
    assert isinstance(a, NoneEmailSender)
