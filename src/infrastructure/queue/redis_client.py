"""
Redis client with connection pooling, retry logic, and circuit breaker pattern.

This module provides a robust Redis client that handles connection failures gracefully
with automatic retries, connection pooling, and circuit breaker protection.
"""

import time
import logging
from typing import Any, Optional, Callable
from contextlib import contextmanager
import redis
from redis.connection import ConnectionPool
from src.core.config import settings

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker implementation to prevent cascading failures."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type[Exception] | tuple[type[Exception], ...] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def _can_attempt_reset(self) -> bool:
        """Check if we can attempt to reset the circuit breaker."""
        if self.state != "OPEN":
            return True
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _record_success(self):
        """Record a successful operation."""
        self.failure_count = 0
        self.state = "CLOSED"

    def _record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        if self.state == "OPEN":
            if not self._can_attempt_reset():
                raise CircuitBreakerOpenException("Circuit breaker is OPEN")
            self.state = "HALF_OPEN"

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except self.expected_exception as e:
            self._record_failure()
            raise e


class CircuitBreakerOpenException(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class RedisClient:
    """Redis client with connection pooling, retry logic, and circuit breaker."""

    def __init__(self):
        self._pool = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=(redis.ConnectionError, redis.TimeoutError, OSError),
        )
        self._max_retries = 3
        self._retry_delay = 1.0

    def _get_connection_pool(self) -> ConnectionPool:
        """Get or create Redis connection pool."""
        if self._pool is None:
            self._pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=10,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True,
            )
        return self._pool

    def _execute_with_retry(self, operation: Callable, *args, **kwargs) -> Any:
        """Execute Redis operation with retry logic and circuit breaker."""
        last_exception = None

        for attempt in range(self._max_retries):
            try:
                return self._circuit_breaker.call(operation, *args, **kwargs)
            except (redis.ConnectionError, redis.TimeoutError, OSError) as e:
                last_exception = e
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2**attempt)  # Exponential backoff
                    logger.warning(
                        f"Redis operation failed (attempt {attempt + 1}/{self._max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Redis operation failed after {self._max_retries} attempts: {e}"
                    )
            except CircuitBreakerOpenException as e:
                logger.warning(
                    f"Circuit breaker is OPEN, skipping Redis operation: {e}"
                )
                raise e

        if last_exception is not None:
            raise last_exception
        else:
            raise Exception("Redis operation failed for unknown reasons")

    def get_client(self) -> redis.Redis:
        """Get a Redis client from the connection pool."""
        return redis.Redis(connection_pool=self._get_connection_pool())

    def ping(self) -> bool:
        """Test Redis connectivity."""
        try:
            client = self.get_client()
            return self._execute_with_retry(client.ping)
        except Exception:
            return False

    def lpush(self, key: str, *values) -> int:
        """Push values to the head of a list."""
        client = self.get_client()
        return self._execute_with_retry(client.lpush, key, *values)

    def blpop(self, keys, timeout: int = 0):
        """Remove and return the first element of a list, or block until one is available."""
        client = self.get_client()
        return self._execute_with_retry(client.blpop, keys, timeout)

    def delete(self, *keys) -> int:
        """Delete one or more keys."""
        client = self.get_client()
        return self._execute_with_retry(client.delete, *keys)

    def llen(self, key: str) -> int:
        """Get the length of a list."""
        client = self.get_client()
        return self._execute_with_retry(client.llen, key)

    def incr(self, key: str) -> int:
        """Increment a key's integer value."""
        client = self.get_client()
        return self._execute_with_retry(client.incr, key)

    def expire(self, key: str, seconds: int) -> bool:
        """Set a key's time to live in seconds."""
        client = self.get_client()
        return self._execute_with_retry(client.expire, key, seconds)

    def get(self, key: str) -> Optional[str]:
        """Get a string key. Returns None when missing."""
        client = self.get_client()
        return self._execute_with_retry(client.get, key)

    def setex(self, key: str, seconds: int, value: str) -> bool:
        """Set a string key with a TTL. Fail closed for callers on Redis errors."""
        client = self.get_client()
        return bool(self._execute_with_retry(client.setex, key, seconds, value))

    def lrange(self, key: str, start: int, end: int):
        """Get a range of elements from a list."""
        client = self.get_client()
        return self._execute_with_retry(client.lrange, key, start, end)

    def flushdb(self):
        """Delete all keys in the current database."""
        client = self.get_client()
        return self._execute_with_retry(client.flushdb)

    def get_circuit_breaker_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "state": self._circuit_breaker.state,
            "failure_count": self._circuit_breaker.failure_count,
            "last_failure_time": self._circuit_breaker.last_failure_time,
        }


# Global Redis client instance
redis_client = RedisClient()


@contextmanager
def redis_connection():
    """Context manager for Redis connections with automatic cleanup."""
    client = redis_client.get_client()
    try:
        yield client
    finally:
        # Connection pool handles cleanup automatically
        pass
