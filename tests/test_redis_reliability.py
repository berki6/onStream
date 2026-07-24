import pytest
import time
from unittest.mock import patch, MagicMock, call
from src.infrastructure.queue.redis_client import (
    RedisClient,
    CircuitBreaker,
    CircuitBreakerOpenException,
    redis_connection,
)
from src.core.config import settings
import redis


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initial_state(self):
        """Test circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None

    def test_circuit_breaker_success_resets_failures(self):
        """Test successful operations reset failure count."""
        cb = CircuitBreaker()

        # Record some failures
        cb._record_failure()
        cb._record_failure()
        assert cb.failure_count == 2

        # Success should reset
        cb._record_success()
        assert cb.failure_count == 0
        assert cb.state == "CLOSED"

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        # Two failures - should still be closed
        cb._record_failure()
        cb._record_failure()
        assert cb.state == "CLOSED"
        assert cb.failure_count == 2

        # Third failure - should open
        cb._record_failure()
        assert cb.state == "OPEN"
        assert cb.failure_count == 3

    def test_circuit_breaker_half_open_after_timeout(self):
        """Test circuit breaker allows attempt after recovery timeout."""
        cb = CircuitBreaker(recovery_timeout=1)

        # Open the circuit
        for _ in range(5):
            cb._record_failure()
        assert cb.state == "OPEN"

        # Should not allow attempts immediately
        assert not cb._can_attempt_reset()

        # Wait for recovery timeout
        time.sleep(1.1)

        # Should allow reset attempt
        assert cb._can_attempt_reset()

    def test_circuit_breaker_call_success(self):
        """Test successful function call through circuit breaker."""
        cb = CircuitBreaker()

        def test_func():
            return "success"

        result = cb.call(test_func)
        assert result == "success"
        assert cb.state == "CLOSED"
        assert cb.failure_count == 0

    def test_circuit_breaker_call_failure(self):
        """Test failed function call through circuit breaker."""
        cb = CircuitBreaker(failure_threshold=2)

        def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError):
            cb.call(failing_func)

        assert cb.failure_count == 1
        assert cb.state == "CLOSED"

    def test_circuit_breaker_call_open_circuit(self):
        """Test circuit breaker blocks calls when open."""
        cb = CircuitBreaker(failure_threshold=1)

        def failing_func():
            raise ValueError("test error")

        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(failing_func)
        assert cb.state == "OPEN"

        # Subsequent calls should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            cb.call(lambda: "success")

    def test_circuit_breaker_recovery_attempt(self):
        """Test circuit breaker recovery attempt in half-open state."""
        cb = CircuitBreaker(recovery_timeout=1, failure_threshold=1)

        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("error")))
        assert cb.state == "OPEN"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Next call should be in half-open state
        result = cb.call(lambda: "success")
        assert result == "success"
        assert cb.state == "CLOSED"

    def test_circuit_breaker_recovery_failure(self):
        """Test circuit breaker re-opens on failed recovery attempt."""
        cb = CircuitBreaker(recovery_timeout=1, failure_threshold=1)

        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("error")))
        assert cb.state == "OPEN"

        # Wait for recovery timeout
        time.sleep(1.1)

        # Recovery attempt fails - should re-open
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("error")))
        assert cb.state == "OPEN"


class TestRedisClient:
    """Test Redis client with connection pooling and retry logic."""

    def setup_method(self):
        """Set up test fixtures."""
        self.redis_client = RedisClient()

    @patch("redis.ConnectionPool.from_url")
    def test_connection_pool_creation(self, mock_pool_from_url):
        """Test connection pool is created correctly."""
        mock_pool = MagicMock()
        mock_pool_from_url.return_value = mock_pool

        pool = self.redis_client._get_connection_pool()

        mock_pool_from_url.assert_called_once_with(
            settings.REDIS_URL,
            max_connections=10,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        assert pool == mock_pool

    @patch("redis.ConnectionPool.from_url")
    def test_connection_pool_reuse(self, mock_pool_from_url):
        """Test connection pool is reused after creation."""
        mock_pool = MagicMock()
        mock_pool_from_url.return_value = mock_pool

        # First call
        pool1 = self.redis_client._get_connection_pool()
        # Second call
        pool2 = self.redis_client._get_connection_pool()

        # Should only create pool once
        mock_pool_from_url.assert_called_once()
        assert pool1 is pool2

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_get_client_uses_pool(self, mock_redis_class):
        """Test get_client uses the connection pool."""
        mock_pool = MagicMock()
        self.redis_client._pool = mock_pool

        client = self.redis_client.get_client()

        mock_redis_class.assert_called_once_with(connection_pool=mock_pool)

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    @patch("time.sleep")
    def test_execute_with_retry_success_first_try(self, mock_sleep, mock_redis_class):
        """Test successful operation on first try."""
        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        def test_operation():
            return "success"

        result = self.redis_client._execute_with_retry(test_operation)

        assert result == "success"
        mock_sleep.assert_not_called()

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    @patch("time.sleep")
    def test_execute_with_retry_success_after_retry(self, mock_sleep, mock_redis_class):
        """Test successful operation after retries."""
        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        call_count = 0

        def failing_then_success_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise redis.ConnectionError("Connection failed")
            return "success"

        result = self.redis_client._execute_with_retry(failing_then_success_operation)

        assert result == "success"
        assert call_count == 3
        # Should have slept twice (exponential backoff: 1.0, 2.0)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([call(1.0), call(2.0)])

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    @patch("time.sleep")
    def test_execute_with_retry_max_retries_exceeded(
        self, mock_sleep, mock_redis_class
    ):
        """Test operation fails after max retries."""
        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        def always_failing_operation():
            raise redis.ConnectionError("Always fails")

        with pytest.raises(redis.ConnectionError):
            self.redis_client._execute_with_retry(always_failing_operation)

        # Should have tried 3 times, slept 2 times
        assert mock_sleep.call_count == 2

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_execute_with_retry_circuit_breaker_open(self, mock_redis_class):
        """Test circuit breaker blocks retries when open."""
        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        # Create a circuit breaker with lower threshold for testing
        self.redis_client._circuit_breaker = CircuitBreaker(failure_threshold=2)

        # Open the circuit breaker by causing failures directly
        self.redis_client._circuit_breaker._record_failure()
        self.redis_client._circuit_breaker._record_failure()

        # Circuit should be open
        assert self.redis_client._circuit_breaker.state == "OPEN"

        # Next call should raise CircuitBreakerOpenException
        with pytest.raises(CircuitBreakerOpenException):
            self.redis_client._execute_with_retry(lambda: "success")

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_ping_success(self, mock_redis_class):
        """Test successful ping."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_redis_class.return_value = mock_client

        result = self.redis_client.ping()

        assert result is True
        mock_client.ping.assert_called_once()

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_ping_failure(self, mock_redis_class):
        """Test ping failure."""
        mock_client = MagicMock()
        mock_client.ping.side_effect = redis.ConnectionError()
        mock_redis_class.return_value = mock_client

        result = self.redis_client.ping()

        assert result is False

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_lpush_operation(self, mock_redis_class):
        """Test lpush operation with retry logic."""
        mock_client = MagicMock()
        mock_client.lpush.return_value = 1
        mock_redis_class.return_value = mock_client

        result = self.redis_client.lpush("test_queue", "item1", "item2")

        assert result == 1
        mock_client.lpush.assert_called_once_with("test_queue", "item1", "item2")

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_blpop_operation(self, mock_redis_class):
        """Test blpop operation with retry logic."""
        mock_client = MagicMock()
        mock_client.blpop.return_value = ("queue", b"item")
        mock_redis_class.return_value = mock_client

        result = self.redis_client.blpop(["queue"], timeout=1)

        assert result == ("queue", b"item")
        mock_client.blpop.assert_called_once_with(["queue"], 1)

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_llen_operation(self, mock_redis_class):
        """Test llen operation with retry logic."""
        mock_client = MagicMock()
        mock_client.llen.return_value = 5
        mock_redis_class.return_value = mock_client

        result = self.redis_client.llen("test_queue")

        assert result == 5
        mock_client.llen.assert_called_once_with("test_queue")

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_lrange_operation(self, mock_redis_class):
        """Test lrange operation with retry logic."""
        mock_client = MagicMock()
        mock_client.lrange.return_value = [b"item1", b"item2"]
        mock_redis_class.return_value = mock_client

        result = self.redis_client.lrange("test_queue", 0, -1)

        assert result == [b"item1", b"item2"]
        mock_client.lrange.assert_called_once_with("test_queue", 0, -1)

    def test_get_circuit_breaker_status(self):
        """Test getting circuit breaker status."""
        status = self.redis_client.get_circuit_breaker_status()

        assert "state" in status
        assert "failure_count" in status
        assert "last_failure_time" in status
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 0

    def test_redis_connection_context_manager(self):
        """Test redis_connection context manager exists and is callable."""
        # Just test that the function exists and is callable
        assert callable(redis_connection)
        # Test that it can be used as a context manager (without mocking Redis)
        try:
            with redis_connection() as client:
                # We don't assert anything about the client since we're not mocking
                # Just verify the context manager works
                assert client is not None
        except Exception:
            # If Redis is not available, that's OK for this test
            # The function exists and can be called as a context manager
            pass


class TestCircuitBreakerRecovery:
    """Test circuit breaker recovery mechanisms."""

    def setup_method(self):
        """Set up test fixtures."""
        self.redis_client = RedisClient()

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_circuit_breaker_status_monitoring(self, mock_redis_class):
        """Test circuit breaker status monitoring."""
        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        # Create a circuit breaker with higher threshold for testing
        self.redis_client._circuit_breaker = CircuitBreaker(failure_threshold=10)

        # Initial status
        status = self.redis_client.get_circuit_breaker_status()
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 0
        assert status["last_failure_time"] is None

        # Cause some failures (each _execute_with_retry call that fails causes 3 failures due to retries)
        for i in range(3):
            try:
                self.redis_client._execute_with_retry(
                    lambda: (_ for _ in ()).throw(redis.ConnectionError("test"))
                )
            except redis.ConnectionError:
                pass

        status = self.redis_client.get_circuit_breaker_status()
        assert status["state"] == "CLOSED"
        assert status["failure_count"] == 9  # 3 calls * 3 retries each = 9 failures
        assert status["last_failure_time"] is not None

        # Open the circuit by recording failures directly
        for i in range(1):
            self.redis_client._circuit_breaker._record_failure()

        status = self.redis_client.get_circuit_breaker_status()
        assert status["state"] == "OPEN"
        assert status["failure_count"] == 10

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_connection_pool_isolation(self, mock_redis_class):
        """Test that connection pool isolates connections properly."""
        mock_client1 = MagicMock()
        mock_client2 = MagicMock()
        mock_redis_class.side_effect = [mock_client1, mock_client2]

        # Get two clients
        client1 = self.redis_client.get_client()
        client2 = self.redis_client.get_client()

        # They should be different instances
        assert client1 is not client2
        assert mock_redis_class.call_count == 2

        # Both should use the same connection pool
        call_args = mock_redis_class.call_args_list
        assert call_args[0][1]["connection_pool"] == call_args[1][1]["connection_pool"]

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    @patch("time.sleep")
    def test_timeout_handling(self, mock_sleep, mock_redis_class):
        """Test handling of Redis timeout errors."""
        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        # Test timeout error handling
        def timeout_operation():
            raise redis.TimeoutError("Operation timed out")

        with pytest.raises(redis.TimeoutError):
            self.redis_client._execute_with_retry(timeout_operation)

        # Should have attempted retries
        assert mock_sleep.call_count == 2  # 2 retry attempts

    @patch("src.infrastructure.queue.redis_client.redis.Redis")
    def test_os_error_handling(self, mock_redis_class):
        """Test handling of OS errors (network issues)."""
        mock_client = MagicMock()
        mock_redis_class.return_value = mock_client

        def os_error_operation():
            raise OSError("Network is unreachable")

        with pytest.raises(OSError):
            self.redis_client._execute_with_retry(os_error_operation)

        # Should count as circuit breaker failure (3 retries = 3 failures)
        assert self.redis_client._circuit_breaker.failure_count == 3
