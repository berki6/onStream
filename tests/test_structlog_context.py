"""Tests for structlog context binding."""

from __future__ import annotations

from src.core import logger as logger_mod
from src.core.logger import bind_context, clear_context, get_logger


def test_bind_context_appears_in_log_output(capsys):
    logger_mod._logger_configured = False
    clear_context()
    bind_context(
        request_id="req-abc",
        upload_id="upld1234",
        stream_id="strmABCDEF12",
        job_type="transcode",
        user_id=42,
    )
    get_logger("test.structlog").info("hello structured world")
    text = capsys.readouterr().out + capsys.readouterr().err
    assert "hello structured world" in text
    assert "req-abc" in text
    assert "upld1234" in text
    assert "strmABCDEF12" in text
    assert "transcode" in text
    clear_context()


def test_clear_context_removes_keys(capsys):
    logger_mod._logger_configured = False
    clear_context()
    bind_context(request_id="should-clear", upload_id="gone")
    clear_context()
    get_logger("test.structlog.clear").info("after clear")
    text = capsys.readouterr().out + capsys.readouterr().err
    assert "after clear" in text
    assert "should-clear" not in text
    assert "gone" not in text
