"""Simple per-IP rate limiting for auth endpoints (Redis with in-memory fallback)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque, Dict

from fastapi import Request

from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

_memory_hits: Dict[str, Deque[float]] = defaultdict(deque)
_lock = Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def check_auth_rate_limit(request: Request) -> None:
    """Raise RATE_LIMIT_EXCEEDED if the client exceeds AUTH_RATE_LIMIT_PER_MINUTE."""
    limit = settings.AUTH_RATE_LIMIT_PER_MINUTE
    if limit <= 0:
        return

    key = f"auth_rl:{_client_ip(request)}"
    window = 60.0
    now = time.time()
    rate_error = AppError(
        "Too many auth attempts. Try again later.",
        code=ErrorCode.RATE_LIMIT_EXCEEDED,
    )

    # Prefer Redis
    try:
        from src.infrastructure.queue.redis_client import redis_client

        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, int(window))
        if count > limit:
            raise rate_error
        return
    except AppError:
        raise
    except Exception as e:
        logger.debug(f"Auth rate limit Redis unavailable, using memory: {e}")

    with _lock:
        hits = _memory_hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= limit:
            raise rate_error
        hits.append(now)
