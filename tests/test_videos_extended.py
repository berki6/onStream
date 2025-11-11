import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.core.database import get_db
from src.schema import models
from tests.conftest import override_get_db
import tempfile
import os

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestVideoRouterExtended:
    """Extended tests for video router endpoints."""

    def test_upload_video_missing_file(self, db_session):
        """Test video upload with missing file field."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="missingfile",
            email="missing@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "missingfile", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Try upload without file
        response = client.post(
            "/videos/",
            data={"title": "No File Video"},
            headers=headers,
        )
        assert response.status_code == 422  # Validation error

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_invalid_content_type(self, db_session):
        """Test video upload with invalid content type."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="invalidtype",
            email="invalidtype@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "invalidtype", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Invalid Type"},
            files={"file": ("test.txt", b"text content", "text/plain")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_title_too_long(self, mocker, db_session):
        """Test video upload with title exceeding max length."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="longtitle",
            email="longtitle@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "longtitle", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        long_title = "A" * 201  # Exceeds MAX_TITLE_LENGTH
        response = client.post(
            "/videos/",
            data={"title": long_title},
            files={"file": ("test.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Title must be" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_corrupt_file(self, mocker, db_session):
        """Test video upload with corrupt/invalid video file."""
        # Mock probe to return None (indicating corrupt file)
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = None

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="corrupt",
            email="corrupt@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "corrupt", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Corrupt Video"},
            files={"file": ("corrupt.mp4", b"not a real video", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Invalid or corrupt video file" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_too_short(self, mocker, db_session):
        """Test video upload with video shorter than minimum duration."""
        # Mock probe to return very short duration
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 0.5  # 0.5 seconds

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="tooshort",
            email="tooshort@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "tooshort", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Too Short Video"},
            files={"file": ("short.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Video is too short" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_too_long(self, mocker, db_session):
        """Test video upload with video longer than maximum duration."""
        # Mock probe to return very long duration
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 7201  # 7201 seconds (just over 2 hours)

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="toolong",
            email="toolong@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "toolong", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Too Long Video"},
            files={"file": ("long.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 400
        assert "Video is too long" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_list_videos_pagination_edge_cases(self, mocker, db_session):
        """Test video listing with edge case pagination parameters."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 60.0

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="paginate",
            email="paginate@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "paginate", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test negative skip
        response = client.get("/videos/?skip=-1", headers=headers)
        assert response.status_code == 400
        assert "must be non-negative" in response.json()["detail"]

        # Test zero limit
        response = client.get("/videos/?limit=0", headers=headers)
        assert response.status_code == 400
        assert "must be between 1 and" in response.json()["detail"]

        # Test negative limit
        response = client.get("/videos/?limit=-1", headers=headers)
        assert response.status_code == 400

        # Test limit exceeding maximum
        response = client.get("/videos/?limit=200", headers=headers)
        assert response.status_code == 400
        assert "must be between 1 and" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_get_video_invalid_upload_id(self, db_session):
        """Test getting video with invalid upload ID format."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="invalidid",
            email="invalidid@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "invalidid", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test upload ID too short
        response = client.get("/videos/abc/", headers=headers)
        assert response.status_code == 400
        assert "Invalid upload ID format" in response.json()["detail"]

        # Test upload ID with invalid characters
        response = client.get("/videos/abcO1234/", headers=headers)
        assert response.status_code == 400
        assert "Invalid upload ID format" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_delete_video_not_found(self, db_session):
        """Test deleting non-existent video."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="deletenotfound",
            email="deletenotfound@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "deletenotfound", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.delete("/videos/abcdefgh/", headers=headers)
        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_delete_video_wrong_user(self, mocker, db_session):
        """Test deleting video owned by another user."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create two users
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")

        user1 = models.User(
            username="deleteowner",
            email="deleteowner@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username="deletestealer",
            email="deletestealer@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login as user1 and create video
        response = client.post(
            "/auth/login", data={"username": "deleteowner", "password": "testpass"}
        )
        token1 = response.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/videos/",
            data={"title": "Owner's Video"},
            files={"file": ("owner.mp4", b"content", "video/mp4")},
            headers=headers1,
        )
        upload_id = response.json()["upload_id"]

        # Login as user2 and try to delete
        response = client.post(
            "/auth/login", data={"username": "deletestealer", "password": "testpass"}
        )
        token2 = response.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.delete(f"/videos/{upload_id}/", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

        # Cleanup
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        if video:
            db_session.delete(video)
        db_session.delete(user1)
        db_session.delete(user2)
        db_session.commit()

    def test_upload_video_auto_title_generation(self, mocker, db_session):
        """Test automatic title generation from filename."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="autotitle",
            email="autotitle@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "autotitle", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload without title - should auto-generate from filename
        response = client.post(
            "/videos/",
            files={"file": ("my_test_video.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Test Video"  # Should be title case

        upload_id = data["upload_id"]

        # Cleanup
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        if video:
            db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_empty_title_fallback(self, mocker, db_session):
        """Test fallback when title is empty and filename is invalid."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="fallback",
            email="fallback@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "fallback", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Upload with empty title and no filename
        response = client.post(
            "/videos/",
            data={"title": ""},
            files={"file": (None, b"content", "video/mp4")},
            headers=headers,
        )
        # This should fail due to missing filename, not title fallback
        assert response.status_code == 422

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_list_videos_empty_result(self, db_session):
        """Test listing videos when user has no videos."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="emptyvideos",
            email="emptyvideos@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "emptyvideos", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/videos/", headers=headers)
        assert response.status_code == 200
        videos = response.json()
        assert videos == []  # Should be empty list

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_get_video_soft_deleted(self, mocker, db_session):
        """Test that soft deleted videos are not accessible."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="softdelete",
            email="softdelete@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "softdelete", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create video
        response = client.post(
            "/videos/",
            data={"title": "Soft Delete Test"},
            files={"file": ("soft.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["upload_id"]

        # Soft delete the video
        response = client.delete(f"/videos/{upload_id}/", headers=headers)
        assert response.status_code == 204

        # Try to access the deleted video
        response = client.get(f"/videos/{upload_id}/", headers=headers)
        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

        # Cleanup
        # The video is already soft deleted, just remove the user
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_database_transaction_failure(self, mocker, db_session):
        """Test video upload when database transaction fails during video creation."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="dbtransfail",
            email="dbtransfail@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "dbtransfail", "password": "Testpass123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Mock database commit to fail only after user creation
        mock_commit = mocker.patch("sqlalchemy.orm.Session.commit")
        mock_commit.side_effect = Exception("Database transaction failed")

        response = client.post(
            "/videos/",
            data={"title": "DB Transaction Fail"},
            files={"file": ("db_fail.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 500
        assert "Failed to create video record" in response.json()["detail"]

        # Cleanup - don't use commit since it's mocked
        try:
            db_session.delete(user)
            # Don't commit during cleanup in this test
        except:
            pass  # Ignore cleanup errors in this test

    def test_upload_video_job_creation_failure(self, mocker, db_session):
        """Test video upload when video job creation fails."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Mock job creation to fail
        mock_create_job = mocker.patch("src.services.crud.create_video_job")
        mock_create_job.side_effect = Exception("Job creation failed")

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="jobfail",
            email="jobfail@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "jobfail", "password": "Testpass123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Job Creation Fail"},
            files={"file": ("job_fail.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 500
        assert "Failed to create processing job" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_file_move_failure(self, mocker, db_session):
        """Test video upload when file move operation fails."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Mock os.rename to fail
        mock_rename = mocker.patch("os.rename")
        mock_rename.side_effect = OSError("File move failed")

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="movefail",
            email="movefail@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "movefail", "password": "Testpass123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "File Move Fail"},
            files={"file": ("move_fail.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 500
        assert "Failed to save video file" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_redis_failure(self, mocker, db_session):
        """Test video upload when Redis queue push fails."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Mock Redis lpush to fail
        mock_redis = mocker.patch("redis.Redis.lpush")
        mock_redis.side_effect = Exception("Redis connection failed")

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="redisfail",
            email="redisfail@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "redisfail", "password": "Testpass123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Redis Fail"},
            files={"file": ("redis_fail.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        # Should still succeed since Redis failure is non-critical
        assert response.status_code == 201
        data = response.json()
        assert "upload_id" in data

        upload_id = data["upload_id"]

        # Cleanup
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        if video:
            db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_upload_video_final_commit_failure(self, mocker, db_session):
        """Test video upload when final database commit fails."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="commitfail",
            email="commitfail@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "commitfail", "password": "Testpass123!"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Mock the final commit in the crud service to fail
        mock_crud_commit = mocker.patch("src.services.crud.Session.commit")
        mock_crud_commit.side_effect = Exception("Final commit failed")

        response = client.post(
            "/videos/",
            data={"title": "Final Commit Fail"},
            files={"file": ("commit_fail.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 500
        assert "Failed to create video record" in response.json()["detail"]

        # Cleanup - don't use commit since it's mocked
        try:
            db_session.delete(user)
            # Don't commit during cleanup in this test
        except:
            pass  # Ignore cleanup errors in this test
