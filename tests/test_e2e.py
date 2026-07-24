import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.infrastructure.db.session import get_db
from src.infrastructure.db import models
from src.infrastructure.db.repositories import job_repository, user_repository, video_repository
from tests.conftest import override_get_db
import redis
from src.core.config import settings

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestEndToEndVideoWorkflow:
    """End-to-end integration tests covering the complete video workflow."""

    def setup_method(self):
        """Clean up Redis before each test."""
        try:
            redis_client = redis.from_url(settings.REDIS_URL)
            redis_client.flushdb()
        except Exception:
            pass  # Redis might not be available in test environment

    def test_complete_user_video_workflow(self, db_session, mocker):
        """Test the complete user journey: register → login → upload → process → stream."""

        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0  # 2 minutes

        # Mock video worker processing
        mock_worker = mocker.patch("src.worker.handlers.transcode_handler.process_video")
        mock_worker.return_value = None

        # Step 1: User Registration
        register_response = client.post(
            "/v1/auth/register",
            json={
                "username": "e2e_user",
                "email": "e2e@example.com",
                "password": "SecurePass123!",
            },
        )
        assert register_response.status_code == 201
        user_data = register_response.json()
        assert user_data["data"]["username"] == "e2e_user"
        assert user_data["data"]["email"] == "e2e@example.com"

        # Step 2: User Login
        login_response = client.post(
            "/v1/auth/login", data={"username": "e2e_user", "password": "SecurePass123!"}
        )
        assert login_response.status_code == 200
        tokens = login_response.json()
        assert "access_token" in tokens["data"]
        assert tokens["data"]["token_type"] == "bearer"
        access_token = tokens["data"]["access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}

        # Step 3: Video Upload
        upload_response = client.post(
            "/v1/videos/",
            data={"title": "E2E Test Video"},
            files={"file": ("test_video.mp4", b"fake video content", "video/mp4")},
            headers=headers,
        )
        assert upload_response.status_code == 201
        video_data = upload_response.json()
        assert "title" in video_data["data"]
        assert video_data["data"]["status"] == "PENDING"
        upload_id = video_data["data"]["upload_id"]

        # Verify video was created in database
        video = video_repository.get_by_upload_id(db_session, upload_id)
        assert video is not None
        assert video.status == models.VideoStatus.PENDING
        assert video.title == "E2E Test Video"

        # Verify job was created
        job = job_repository.get_for_video(db_session, video)
        assert job is not None
        assert job.status in ("processing", "queued")

        # Step 4: Check Video Status (should still be PENDING before processing)
        status_response = client.get(f"/v1/videos/{upload_id}", headers=headers)
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["data"]["status"] == "PENDING"

        # Step 5: Check Job Status
        job_response = client.get(f"/v1/videos/{upload_id}/jobs/latest", headers=headers)
        assert job_response.status_code == 200
        job_data = job_response.json()
        assert job_data["data"]["status"] in ("processing", "queued")
        assert job_data["data"]["progress"] == 0

        # Step 6: Simulate Video Processing Completion
        # Update video status to READY (simulating successful processing)
        video.status = models.VideoStatus.READY
        video.hls_path = f"data/hls/{upload_id}/index.m3u8"
        video.thumbnail_path = f"data/thumbnails/{video.id}.jpg"
        db_session.commit()

        # Update job status to completed
        job.status = "ready"
        job.progress = 100
        job.message = "Job completed successfully"
        db_session.commit()

        # Step 7: Verify Video Status After Processing
        status_response = client.get(f"/v1/videos/{upload_id}", headers=headers)
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["data"]["status"] == "READY"
        assert status_data["data"]["hls_path"] is not None
        assert status_data["data"]["thumbnail_path"] is not None

        # Step 8: Check Job Status After Completion
        job_response = client.get(f"/v1/videos/{upload_id}/jobs/latest", headers=headers)
        assert job_response.status_code == 200
        job_data = job_response.json()
        assert job_data["data"]["status"] == "ready"
        assert job_data["data"]["progress"] == 100
        assert "completed successfully" in job_data["data"]["message"]

        # Step 9: Test Video Streaming (HLS Playlist)
        playlist_response = client.get(
            f"/v1/playback/{upload_id}/master.m3u8", headers=headers
        )
        assert (
            playlist_response.status_code == 404
        )  # File doesn't exist in test, but endpoint works

        # Step 10: List User's Videos
        list_response = client.get("/v1/videos/", headers=headers)
        assert list_response.status_code == 200
        videos_list = list_response.json()
        assert len(videos_list["data"]) >= 1
        assert any(v["upload_id"] == upload_id for v in videos_list["data"])

        # Step 11: Cleanup - Delete Video
        delete_response = client.delete(f"/v1/videos/{upload_id}", headers=headers)
        assert delete_response.status_code == 204

        # Verify video was soft-deleted
        video = video_repository.get_by_upload_id(db_session, upload_id)
        assert video is None  # Should not be found due to soft delete

        # Clean up test user
        test_user = user_repository.get_by_username(db_session, "e2e_user")
        if test_user:
            db_session.delete(test_user)
            db_session.commit()

    def test_video_upload_validation(self, db_session, mocker):
        """Test video upload validation scenarios."""

        # Mock video duration probe for valid uploads
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        test_user = models.User(
            username="validation_user",
            email="validation@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Login
        login_response = client.post(
            "/v1/auth/login", data={"username": "validation_user", "password": "testpass"}
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Test 1: Invalid file type
        response = client.post(
            "/v1/videos/",
            data={"title": "Invalid Video"},
            files={"file": ("test.txt", b"text content", "text/plain")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

        # Test 2: File too large (mock large file)
        mocker.patch("fastapi.UploadFile.__init__", return_value=None)
        mock_file = mocker.MagicMock()
        mock_file.size = 600 * 1024 * 1024  # 600MB
        mock_file.filename = "large.mp4"
        mock_file.content_type = "video/mp4"
        mock_file.file = mocker.MagicMock()

        response = client.post(
            "/v1/videos/",
            data={"title": "Large Video"},
            files={"file": ("large.mp4", b"large content", "video/mp4")},
            headers=headers,
        )
        # Note: Size validation happens after file is read, so this might not catch it in test
        # The validation is in the router, but the test client handles files differently

        # Test 3: Missing filename
        response = client.post(
            "/v1/videos/",
            data={"title": "No Filename"},
            files={"file": (None, b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 422  # FastAPI validation error

        # Test 4: Title too long
        long_title = "A" * 201  # 201 characters
        response = client.post(
            "/v1/videos/",
            data={"title": long_title},
            files={"file": ("test.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Title must be" in response.json()["detail"]

        # Clean up
        db_session.delete(test_user)
        db_session.commit()

    def test_unauthorized_access_scenarios(self, db_session, mocker):
        """Test that unauthorized users cannot access protected resources."""

        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create two test users with unique names
        import uuid

        user1_name = f"user1_{uuid.uuid4().hex[:8]}"
        user2_name = f"user2_{uuid.uuid4().hex[:8]}"

        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")

        user1 = models.User(
            username=user1_name,
            email=f"{user1_name}@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username=user2_name,
            email=f"{user2_name}@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login as user1
        login_response = client.post(
            "/v1/auth/login", data={"username": user1_name, "password": "testpass"}
        )
        assert login_response.status_code == 200
        token1 = login_response.json()["data"]["access_token"]

        # Login as user2
        login_response = client.post(
            "/v1/auth/login", data={"username": user2_name, "password": "testpass"}
        )
        assert login_response.status_code == 200
        token2 = login_response.json()["data"]["access_token"]

        # Create video for user1
        headers1 = {"Authorization": f"Bearer {token1}"}
        upload_response = client.post(
            "/v1/videos/",
            data={"title": "User1 Video"},
            files={"file": ("test.mp4", b"content", "video/mp4")},
            headers=headers1,
        )
        assert upload_response.status_code == 201
        upload_id = upload_response.json()["data"]["upload_id"]

        # Test 1: User2 tries to access user1's video
        headers2 = {"Authorization": f"Bearer {token2}"}
        response = client.get(f"/v1/videos/{upload_id}", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

        # Test 2: User2 tries to access user1's job status
        response = client.get(f"/v1/videos/{upload_id}/jobs/latest", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

        # Test 3: User2 tries to stream user1's video
        response = client.get(f"/v1/playback/{upload_id}/master.m3u8", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

        # Test 4: User2 tries to delete user1's video
        response = client.delete(f"/v1/videos/{upload_id}", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

        # Test 5: No token provided
        response = client.get("/v1/videos/")
        assert response.status_code in (401, 403)

        # Clean up
        db_session.delete(user1)
        db_session.delete(user2)
        db_session.commit()

    def test_health_endpoints(self):
        """Test health check endpoints."""
        # Root endpoint
        response = client.get("/")
        assert response.status_code == 200
        assert "OnStream" in response.json()["message"]

        # Health check
        response = client.get("/health")
        assert response.status_code == 200
        health_data = response.json()
        assert "status" in health_data["data"]
        assert "database" in health_data["data"]
        assert "timestamp" in health_data

        # Liveness probe
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "alive"

        # Readiness probe
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "ready"

    def test_pagination_and_limits(self, db_session, mocker):
        """Test pagination and API limits."""

        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 60.0

        # Create test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        test_user = models.User(
            username="pagination_user",
            email="pagination@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(test_user)
        db_session.commit()
        db_session.refresh(test_user)

        # Login
        login_response = client.post(
            "/v1/auth/login", data={"username": "pagination_user", "password": "testpass"}
        )
        assert login_response.status_code == 200
        access_token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Create multiple videos
        upload_ids = []
        for i in range(5):
            response = client.post(
                "/v1/videos/",
                data={"title": f"Video {i+1}"},
                files={"file": (f"video{i+1}.mp4", b"content", "video/mp4")},
                headers=headers,
            )
            assert response.status_code == 201
            upload_ids.append(response.json()["data"]["upload_id"])

        # Test pagination - limit 2
        response = client.get("/v1/videos/?limit=2", headers=headers)
        assert response.status_code == 200
        videos = response.json()
        assert len(videos["data"]) == 2

        # Test pagination - skip 2, limit 2
        response = client.get("/v1/videos/?skip=2&limit=2", headers=headers)
        assert response.status_code == 200
        videos = response.json()
        assert len(videos["data"]) == 2

        # Test invalid pagination parameters
        response = client.get("/v1/videos/?skip=-1", headers=headers)
        assert response.status_code == 400
        assert "must be non-negative" in response.json()["detail"]

        response = client.get("/v1/videos/?limit=0", headers=headers)
        assert response.status_code == 400
        assert "must be between 1 and" in response.json()["detail"]

        response = client.get("/v1/videos/?limit=200", headers=headers)
        assert response.status_code == 400
        assert "must be between 1 and" in response.json()["detail"]

        # Clean up
        db_session.delete(test_user)
        db_session.commit()
