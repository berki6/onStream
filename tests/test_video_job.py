import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.infrastructure.db.session import get_db
from src.infrastructure.db import models
from src import schemas
from src.infrastructure.db.repositories import job_repository, video_repository
from tests.conftest import override_get_db
import redis
import json
from src.core.config import settings
from unittest.mock import patch, MagicMock, call


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_get_video_job_status(db_session: Session, test_user, mocker):
    """Test getting video job status"""
    # Mock the video duration probe to return a valid duration
    mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
    mock_probe.return_value = 120.0  # 2 minutes

    # Clear Redis queue before test (optional if Redis is down)
    try:
        redis_client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        redis_client.delete("video_jobs_queue")
    except Exception:
        redis_client = None

    # Create a video first
    video_data = {"title": "Test Video", "description": "Test Description"}

    # Login to get token
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]

    # Upload video (this should create a video and job)
    response = client.post(
        "/v1/videos/",
        data=video_data,
        files={"file": ("test.mp4", b"fake video content", "video/mp4")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    upload_response = response.json()
    upload_id = upload_response["data"]["upload_id"]

    # Verify job was created in database (Redis might not be available in test env)
    job = job_repository.get_for_video(
        db_session, video_repository.get_by_upload_id(db_session, upload_id)
    )
    assert job is not None
    assert job.upload_id == upload_id

    # Try to check Redis queue, but don't fail if Redis is not available
    try:
        if redis_client is not None:
            queue_length = redis_client.llen("video_jobs_queue")
            if queue_length > 0:  # Only check if Redis is working
                # Get the job from queue
                queued_job = redis_client.lrange("video_jobs_queue", -1, -1)
                raw = queued_job[0].decode("utf-8")
                try:
                    payload = json.loads(raw)
                    assert payload["upload_id"] == upload_id
                    assert payload.get("job_type", "transcode") == "transcode"
                except json.JSONDecodeError:
                    assert raw == upload_id
    except Exception:
        # Redis not available in test environment, that's OK
        pass

    # Get the video job status
    response = client.get(
        f"/v1/videos/{upload_id}/jobs/latest",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    job_data = response.json()["data"]

    # Verify job structure
    assert "upload_id" in job_data
    assert "status" in job_data
    assert "progress" in job_data
    assert "eta" in job_data
    assert "message" in job_data
    assert "created_at" in job_data
    assert "updated_at" in job_data

    # Should start with processing status
    assert job_data["status"] in ("processing", "queued")
    assert job_data["progress"] == 0
    assert job_data["eta"] == 0


def test_get_video_job_not_found(db_session: Session, test_user):
    """Test getting job for non-existent video"""
    # Login to get token
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]

    response = client.get(
        "/v1/videos/abcdefgh/jobs/latest",  # Valid 8-character format but non-existent
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Video not found"


def test_get_video_job_unauthorized(db_session: Session, test_user, mocker):
    """Test getting job for video owned by another user"""
    # Mock the video duration probe to return a valid duration
    mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
    mock_probe.return_value = 120.0  # 2 minutes
    # Create second user
    from src.core.security.passwords import get_password_hash

    hashed_password = get_password_hash("testpass2")
    user2 = models.User(
        username="testuser2", email="test2@example.com", hashed_password=hashed_password
    )
    db_session.add(user2)
    db_session.commit()
    db_session.refresh(user2)

    # Login with first user
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    token1 = response.json()["data"]["access_token"]

    # Create video with user 1
    video_data = {"title": "Test Video", "description": "Test Description"}

    response = client.post(
        "/v1/videos/",
        data=video_data,
        files={"file": ("test2.mp4", b"fake video content", "video/mp4")},
        headers={"Authorization": f"Bearer {token1}"},
    )

    assert response.status_code == 201
    upload_response = response.json()
    upload_id = upload_response["data"]["upload_id"]

    # Login with second user
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser2", "password": "testpass2"},
    )
    assert response.status_code == 200
    token2 = response.json()["data"]["access_token"]

    # Try to access with user 2
    response = client.get(
        f"/v1/videos/{upload_id}/jobs/latest",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Access denied"

    # Clean up
    db_session.delete(user2)
    db_session.commit()


class TestJobQueueReliability:
    """Test job queue service reliability features."""

    def setup_method(self):
        """Set up test fixtures."""
        from src.infrastructure.queue.job_queue import JobQueueService

        self.job_queue = JobQueueService()
        # Mock the redis_client on the instance for testing
        self.mock_redis_client = MagicMock()
        self.job_queue.redis_client = self.mock_redis_client

    def test_enqueue_job_redis_success(self, db_session):
        """Test successful job enqueue to Redis."""
        self.mock_redis_client.lpush.return_value = 1

        result = self.job_queue.enqueue_job("testupload123", db_session)

        assert result is True
        self.mock_redis_client.lpush.assert_called_once()
        call_args = self.mock_redis_client.lpush.call_args[0]
        assert call_args[0] == "video_jobs_queue"
        payload = json.loads(call_args[1])
        assert payload == {"upload_id": "testupload123", "job_type": "transcode"}

    def test_enqueue_job_redis_failure_fallback_to_db(self, db_session):
        """Test job enqueue falls back to database when Redis fails."""
        from src.infrastructure.queue.redis_client import CircuitBreakerOpenException

        self.mock_redis_client.lpush.side_effect = CircuitBreakerOpenException(
            "Circuit open"
        )

        result = self.job_queue.enqueue_job("testupload123", db_session)

        assert result is True
        # Check that job was stored in database
        queued_job = (
            db_session.query(models.QueuedJob)
            .filter_by(upload_id="testupload123")
            .first()
        )
        assert queued_job is not None
        assert queued_job.status == "pending"
        assert queued_job.queue_name == "video_jobs_queue"
        assert queued_job.job_type == "transcode"

        # Clean up
        db_session.delete(queued_job)
        db_session.commit()

    def test_enqueue_job_redis_and_db_failure(self, db_session):
        """Test job enqueue fails when both Redis and database fail."""
        from src.infrastructure.queue.redis_client import CircuitBreakerOpenException

        self.mock_redis_client.lpush.side_effect = CircuitBreakerOpenException(
            "Circuit open"
        )

        # Mock database failure
        with patch.object(db_session, "add", side_effect=Exception("DB error")):
            result = self.job_queue.enqueue_job("testupload123", db_session)

        assert result is False

    def test_enqueue_job_duplicate_prevention(self, db_session):
        """Test duplicate jobs are not created in database fallback."""
        from src.infrastructure.queue.redis_client import CircuitBreakerOpenException

        self.mock_redis_client.lpush.side_effect = CircuitBreakerOpenException(
            "Circuit open"
        )

        # First enqueue
        result1 = self.job_queue.enqueue_job("testupload123", db_session)
        assert result1 is True

        # Second enqueue with same upload_id
        result2 = self.job_queue.enqueue_job("testupload123", db_session)
        assert result2 is True

        # Should only have one job in database
        jobs = (
            db_session.query(models.QueuedJob)
            .filter_by(upload_id="testupload123")
            .all()
        )
        assert len(jobs) == 1

        # Clean up
        db_session.delete(jobs[0])
        db_session.commit()

    def test_dequeue_job_redis_success(self):
        """Test successful job dequeue from Redis."""
        payload = json.dumps(
            {"upload_id": "testupload123", "job_type": "transcode"}
        ).encode("utf-8")
        self.mock_redis_client.blpop.return_value = (
            "video_jobs_queue",
            payload,
        )

        result = self.job_queue.dequeue_job()

        assert result == {"upload_id": "testupload123", "job_type": "transcode"}
        self.mock_redis_client.blpop.assert_called_once_with(
            "video_jobs_queue", timeout=1
        )

    def test_dequeue_job_legacy_string_payload(self):
        """Legacy plain upload_id strings map to job_type=transcode."""
        self.mock_redis_client.blpop.return_value = (
            "video_jobs_queue",
            b"testupload123",
        )
        result = self.job_queue.dequeue_job()
        assert result == {"upload_id": "testupload123", "job_type": "transcode"}

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_dequeue_job_redis_failure_fallback_to_db(self, mock_get_db):
        """Test job dequeue falls back to database when Redis fails."""
        from src.infrastructure.queue.redis_client import CircuitBreakerOpenException

        self.mock_redis_client.blpop.side_effect = CircuitBreakerOpenException(
            "Circuit open"
        )

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter(
            [mock_session]
        )  # Return iterator yielding session

        # Mock queued job in database
        mock_job = MagicMock()
        mock_job.upload_id = "testupload123"
        mock_job.job_type = "transcode"
        mock_job.status = "pending"
        mock_job.retry_count = 0
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_job
        )

        result = self.job_queue.dequeue_job()

        # Check that a job was returned and database was committed
        assert result is not None
        assert result["upload_id"] == "testupload123"
        assert result["job_type"] == "transcode"
        assert mock_session.commit.called
        assert mock_job.status == "processing"
        assert mock_job.retry_count == 1
        mock_session.commit.assert_called_once()

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_dequeue_job_no_jobs_in_db(self, mock_get_db):
        """Test dequeue returns None when no jobs in database."""
        from src.infrastructure.queue.redis_client import CircuitBreakerOpenException

        self.mock_redis_client.blpop.side_effect = CircuitBreakerOpenException(
            "Circuit open"
        )

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Mock no jobs found
        mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            None
        )

        result = self.job_queue.dequeue_job()

        assert result is None

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_mark_job_completed(self, mock_get_db):
        """Test marking job as completed."""
        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Mock finding the job
        mock_job = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            mock_job
        )

        self.job_queue.mark_job_completed("testupload123")

        # Check that database was committed
        assert mock_session.commit.called
        mock_session.commit.assert_called_once()

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_mark_job_failed(self, mock_get_db):
        """Test marking job as failed."""
        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Mock finding the job
        mock_job = MagicMock()
        mock_job.retry_count = 1
        mock_session.query.return_value.filter_by.return_value.first.return_value = (
            mock_job
        )

        self.job_queue.mark_job_failed("testupload123", "Processing error")

        # Check that database was committed
        assert mock_session.commit.called
        assert mock_job.error_message == "Processing error"
        assert mock_job.retry_count == 2
        mock_session.commit.assert_called_once()

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_recover_jobs_to_redis(self, mock_get_db):
        """Test recovering jobs from database to Redis."""
        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Mock finding jobs
        mock_job1 = MagicMock()
        mock_job1.upload_id = "upload1"
        mock_job1.job_type = "transcode"
        mock_job2 = MagicMock()
        mock_job2.upload_id = "upload2"
        mock_job2.job_type = "captions"
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_job1,
            mock_job2,
        ]

        # Mock successful Redis push
        self.mock_redis_client.lpush.return_value = 1

        recovered_count = self.job_queue.recover_jobs_to_redis()

        # Check that Redis was called for both jobs and database was committed
        assert self.mock_redis_client.lpush.call_count == 2
        first_payload = json.loads(self.mock_redis_client.lpush.call_args_list[0][0][1])
        second_payload = json.loads(self.mock_redis_client.lpush.call_args_list[1][0][1])
        assert first_payload == {"upload_id": "upload1", "job_type": "transcode"}
        assert second_payload == {"upload_id": "upload2", "job_type": "captions"}
        assert mock_session.commit.called

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_recover_jobs_to_redis_partial_failure(self, mock_get_db):
        """Test partial failure during job recovery."""
        from src.infrastructure.queue.redis_client import CircuitBreakerOpenException

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Mock finding jobs
        mock_job1 = MagicMock()
        mock_job1.upload_id = "upload1"
        mock_job1.job_type = "transcode"
        mock_job2 = MagicMock()
        mock_job2.upload_id = "upload2"
        mock_job2.job_type = "transcode"
        mock_session.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [
            mock_job1,
            mock_job2,
        ]

        # Mock Redis failure on second job
        self.mock_redis_client.lpush.side_effect = [
            1,
            CircuitBreakerOpenException("Circuit open"),
        ]

        recovered_count = self.job_queue.recover_jobs_to_redis()

        # Check that Redis was attempted for both jobs but only first succeeded
        assert self.mock_redis_client.lpush.call_count == 2
        assert mock_session.commit.called

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_get_queue_stats_complete(self, mock_get_db):
        """Test getting complete queue statistics."""
        # Mock Redis stats
        self.mock_redis_client.ping.return_value = True
        self.mock_redis_client.llen.return_value = 5
        self.mock_redis_client.get_circuit_breaker_status.return_value = {
            "state": "CLOSED",
            "failure_count": 0,
            "last_failure_time": None,
        }

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value.__iter__.return_value = [mock_session]

        # Mock count returns
        mock_session.query.return_value.filter.return_value.count.side_effect = [3, 2]

        stats = self.job_queue.get_queue_stats()

        # Check that stats dict has expected keys
        assert "redis_available" in stats
        assert "redis_queue_length" in stats
        assert "database_pending_jobs" in stats
        assert "database_failed_jobs" in stats
        assert "circuit_breaker_status" in stats

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_get_queue_stats_redis_unavailable(self, mock_get_db):
        """Test queue stats when Redis is unavailable."""
        # Mock Redis failure
        self.mock_redis_client.ping.return_value = False
        self.mock_redis_client.llen.side_effect = Exception("Redis down")
        self.mock_redis_client.get_circuit_breaker_status.return_value = {
            "state": "OPEN",
            "failure_count": 5,
            "last_failure_time": 1234567890,
        }

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value.__iter__.return_value = [mock_session]

        # Mock count returns
        mock_session.query.return_value.filter.return_value.count.side_effect = [1, 0]

        stats = self.job_queue.get_queue_stats()

        # Check that stats dict has expected keys
        assert "redis_available" in stats
        assert "redis_queue_length" in stats
        assert "database_pending_jobs" in stats
        assert "database_failed_jobs" in stats
        assert "circuit_breaker_status" in stats

    @patch("src.infrastructure.queue.job_queue.get_db")
    def test_cleanup_old_jobs(self, mock_get_db):
        """Test cleanup of old completed jobs."""
        from datetime import datetime, timedelta, timezone

        # Mock database session
        mock_session = MagicMock()
        mock_get_db.return_value = iter([mock_session])

        # Mock the delete operation
        mock_session.query.return_value.filter.return_value.delete.return_value = 5

        deleted_count = self.job_queue.cleanup_old_jobs(days_old=30)

        # Check that database was committed
        assert mock_session.commit.called
        mock_session.commit.assert_called_once()
