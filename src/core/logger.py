"""Structured logging with structlog + stdlib bridge."""

from __future__ import annotations

import asyncio
import contextvars
import functools
import logging
import sys
import time
from typing import Any, Optional

import structlog
from structlog.contextvars import (
    bind_contextvars,
    clear_contextvars,
    get_contextvars,
)

from src.core.config import settings

_logger_configured = False

CONTEXT_KEYS = (
    "request_id",
    "upload_id",
    "stream_id",
    "job_type",
    "user_id",
)

# Backward-compatible ContextVar used by middleware / callers
request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default=""
)


def bind_context(**kwargs: Any) -> None:
    """Bind request-scoped fields into structlog contextvars (and request_id_context)."""
    cleaned = {}
    for key, value in kwargs.items():
        if key not in CONTEXT_KEYS or value is None:
            continue
        cleaned[key] = value
        if key == "request_id":
            request_id_context.set(str(value))
    if cleaned:
        bind_contextvars(**cleaned)


def clear_context() -> None:
    """Clear all bound logging context."""
    clear_contextvars()
    request_id_context.set("")


def _inject_legacy_request_id(
    logger: Any, method_name: str, event_dict: dict
) -> dict:
    """Ensure request_id from legacy ContextVar appears if not already bound."""
    if not event_dict.get("request_id"):
        rid = request_id_context.get()
        if rid:
            event_dict["request_id"] = rid
    return event_dict


def _configure_structlog() -> None:
    global _logger_configured
    if _logger_configured:
        return

    log_level = getattr(settings, "LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, str(log_level).upper(), logging.INFO)
    log_filename = getattr(settings, "LOG_FILE", "python.log")
    is_production = getattr(settings, "ENV", "development") == "production"

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        _inject_legacy_request_id,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if is_production:
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=False)

    structlog.configure(
        processors=shared_processors
        + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    root_logger.setLevel(numeric_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    try:
        file_handler = logging.FileHandler(log_filename, mode="a", encoding="utf-8")
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError:
        pass

    # Optional Sentry integration
    try:
        if getattr(settings, "SENTRY_DSN", ""):
            import sentry_sdk

            sentry_sdk.init(dsn=settings.SENTRY_DSN)
    except Exception:
        pass  # nosec B110

    _logger_configured = True


def get_logger(name: Optional[str] = None):
    """
    Return a stdlib logger configured for OnStream.

    Bound context (request_id, upload_id, …) is merged into every log line
    via structlog's ProcessorFormatter bridge.
    """
    _configure_structlog()
    return logging.getLogger(name)


def log_timing(logger=None):
    """Decorator to log execution time of sync and async functions."""

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            result = await func(*args, **kwargs)
            elapsed = time.time() - start
            log = logger or get_logger(func.__module__)
            log.info(f"[TIMING] {func.__name__} took {elapsed:.2f}s")
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            log = logger or get_logger(func.__module__)
            log.info(f"[TIMING] {func.__name__} took {elapsed:.2f}s")
            return result

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# Re-export for callers that want to inspect bound fields
__all__ = [
    "bind_context",
    "clear_context",
    "get_logger",
    "log_timing",
    "request_id_context",
    "CONTEXT_KEYS",
    "get_contextvars",
]
