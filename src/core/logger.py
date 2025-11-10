import logging

from src.core.config import settings


_logger_configured = False

def get_logger(name=None):
    """
    Returns a logger with the specified name, configured for the project.
    Honors LOG_LEVEL from settings and initializes Sentry if SENTRY_DSN is set.
    """

    global _logger_configured
    root_logger = logging.getLogger()
    if _logger_configured:
        return logging.getLogger(name)

    # Configure root logger
    log_level = getattr(settings, "LOG_LEVEL", "INFO")
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    log_filename = getattr(
        settings,
        "LOG_FILE",
        numeric_level >= logging.WARNING and "log/error.log" or "log/flask_app.log",
    )
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Set level
    root_logger.setLevel(numeric_level)

    # File handler
    file_handler = logging.FileHandler(log_filename, mode="w", encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    root_logger.addHandler(console_handler)

    # Optional Sentry integration
    try:
        if getattr(settings, "SENTRY_DSN", ""):
            import sentry_sdk

            sentry_sdk.init(dsn=settings.SENTRY_DSN)
    except Exception:
        # Do not fail startup if sentry isn't installed or fails to init
        pass  # nosec B110

    _logger_configured = True
    return logging.getLogger(name)


import asyncio

# --- Timing Decorators ---
import functools
import time


def log_timing(logger=None):
    """
    Decorator to log execution time of sync and async functions.
    """

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
        else:
            return sync_wrapper

    return decorator
