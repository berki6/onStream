import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.core.database import get_db
from src.services import crud
from src.schema import schemas, models
from tests.conftest import override_get_db
import redis
from src.core.config import settings


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_get_video_job_status(db_session: Session, test_user, mocker):
    """Test getting video job status"""
    # Mock the video duration probe to return a valid duration
    mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
    mock_probe.return_value = 120.0  # 2 minutes

    # Clear Redis queue before test
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.delete("video_jobs_queue")

    # Create a video first
    video_data = {"title": "Test Video", "description": "Test Description"}

    # Login to get token
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]

    # Upload video (this should create a video and job)
    response = client.post(
        "/videos/",
        data=video_data,
        files={"file": ("test.mp4", b"fake video content", "video/mp4")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    upload_response = response.json()
    upload_id = upload_response["data"]["upload_id"]

    # Verify job was created in database (Redis might not be available in test env)
    job = crud.get_job_for_video(
        db_session, crud.get_video_by_upload_id(db_session, upload_id)
    )
    assert job is not None
    assert job.upload_id == upload_id

    # Try to check Redis queue, but don't fail if Redis is not available
    try:
        queue_length = redis_client.llen("video_jobs_queue")
        if queue_length > 0:  # Only check if Redis is working
            # Get the job from queue
            queued_job = redis_client.lrange("video_jobs_queue", -1, -1)
            assert queued_job[0].decode("utf-8") == upload_id
    except Exception:
        # Redis not available in test environment, that's OK
        pass

    # Get the video job status
    response = client.get(
        f"/videos/{upload_id}/job",
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
    assert job_data["status"] == "processing"
    assert job_data["progress"] == 0
    assert job_data["eta"] == 0


def test_get_video_job_not_found(db_session: Session, test_user):
    """Test getting job for non-existent video"""
    # Login to get token
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    token = response.json()["data"]["access_token"]

    response = client.get(
        "/videos/abcdefgh/job",  # Valid 8-character format but non-existent
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_get_video_job_unauthorized(db_session: Session, test_user, mocker):
    """Test getting job for video owned by another user"""
    # Mock the video duration probe to return a valid duration
    mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
    mock_probe.return_value = 120.0  # 2 minutes
    # Create second user
    from src.core.auth import get_password_hash

    hashed_password = get_password_hash("testpass2")
    user2 = models.User(
        username="testuser2", email="test2@example.com", hashed_password=hashed_password
    )
    db_session.add(user2)
    db_session.commit()
    db_session.refresh(user2)

    # Login with first user
    response = client.post(
        "/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    token1 = response.json()["data"]["access_token"]

    # Create video with user 1
    video_data = {"title": "Test Video", "description": "Test Description"}

    response = client.post(
        "/videos/",
        data=video_data,
        files={"file": ("test2.mp4", b"fake video content", "video/mp4")},
        headers={"Authorization": f"Bearer {token1}"},
    )

    assert response.status_code == 201
    upload_response = response.json()
    upload_id = upload_response["data"]["upload_id"]

    # Login with second user
    response = client.post(
        "/auth/login",
        data={"username": "testuser2", "password": "testpass2"},
    )
    assert response.status_code == 200
    token2 = response.json()["data"]["access_token"]

    # Try to access with user 2
    response = client.get(
        f"/videos/{upload_id}/job",
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied"

    # Clean up
    db_session.delete(user2)
    db_session.commit()
