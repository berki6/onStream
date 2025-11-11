import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.core.database import get_db
from src.schema import models
from tests.conftest import override_get_db
import tempfile
import os
from unittest.mock import patch

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestStreamRouter:
    """Test HLS streaming endpoints."""

    def test_stream_playlist_success(self, db_session, mocker):
        """Test successful HLS playlist streaming."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.routers.videos.probe_video_duration")
        mock_probe.return_value = 120.0

        # Create test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="streamuser",
            email="stream@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Login
        response = client.post(
            "/auth/login", data={"username": "streamuser", "password": "testpass"}
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create and process video
        response = client.post(
            "/videos/",
            data={"title": "Stream Test Video"},
            files={"file": ("stream.mp4", b"fake content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 201
        upload_id = response.json()["upload_id"]

        # Update video to READY status with HLS path
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        # Create temporary HLS directory and playlist file
        hls_dir = os.path.join("data", "hls", upload_id)
        os.makedirs(hls_dir, exist_ok=True)
        playlist_path = os.path.join(hls_dir, "index.m3u8")

        playlist_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXTINF:10.0,
segment_000.ts
#EXT-X-ENDLIST
"""
        with open(playlist_path, "w") as f:
            f.write(playlist_content)

        video.hls_path = playlist_path
        db_session.commit()

        # Test playlist streaming
        response = client.get(f"/stream/{upload_id}/playlist.m3u8", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.apple.mpegurl"
        assert "#EXTM3U" in response.text
        assert "segment_000.ts" in response.text

        # Cleanup
        import shutil

        if os.path.exists(hls_dir):
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_stream_playlist_invalid_upload_id(self):
        """Test streaming with invalid upload ID format."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="invaliduser",
            email="invalid@example.com",
            hashed_password=hashed_password,
        )
        db_session = next(override_get_db())
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "invaliduser", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test invalid upload ID (too short)
        response = client.get("/stream/abc/playlist.m3u8", headers=headers)
        assert response.status_code == 400
        assert "Invalid upload ID format" in response.json()["detail"]

        # Test invalid upload ID (wrong characters)
        response = client.get("/stream/abcO1234/playlist.m3u8", headers=headers)
        assert response.status_code == 400
        assert "Invalid upload ID format" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_stream_playlist_video_not_found(self):
        """Test streaming playlist for non-existent video."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="notfounduser",
            email="notfound@example.com",
            hashed_password=hashed_password,
        )
        db_session = next(override_get_db())
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "notfounduser", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/stream/abcdefgh/playlist.m3u8", headers=headers)
        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    @patch("src.routers.videos.probe_video_duration", return_value=120.0)
    def test_stream_playlist_unauthorized(self, mock_probe):
        """Test streaming playlist for video owned by another user."""
        db_session = next(override_get_db())

        # Create two users
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")

        user1 = models.User(
            username="owneruser",
            email="owner@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username="otheruser",
            email="other@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login as user2
        response = client.post(
            "/auth/login", data={"username": "otheruser", "password": "testpass"}
        )
        token2 = response.json()["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Create video for user1
        response = client.post(
            "/auth/login", data={"username": "owneruser", "password": "testpass"}
        )
        token1 = response.json()["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/videos/",
            data={"title": "Private Video"},
            files={"file": ("private.mp4", b"content", "video/mp4")},
            headers=headers1,
        )
        upload_id = response.json()["upload_id"]

        # Try to access with user2
        response = client.get(f"/stream/{upload_id}/playlist.m3u8", headers=headers2)
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

    @patch("src.routers.videos.probe_video_duration", return_value=120.0)
    def test_stream_playlist_video_not_ready(self, mock_probe):
        """Test streaming playlist for video that is not ready."""
        db_session = next(override_get_db())

        # Create user and video in PENDING status
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="pendinguser",
            email="pending@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "pendinguser", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Pending Video"},
            files={"file": ("pending.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["upload_id"]

        # Try to stream before processing
        response = client.get(f"/stream/{upload_id}/playlist.m3u8", headers=headers)
        assert response.status_code == 409
        assert "Video is not ready for streaming" in response.json()["detail"]

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

    @patch("src.routers.videos.probe_video_duration", return_value=120.0)
    def test_stream_playlist_missing_file(self, mock_probe):
        """Test streaming playlist when HLS file doesn't exist."""
        db_session = next(override_get_db())

        # Create user and video
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="missinguser",
            email="missing@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "missinguser", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Missing HLS Video"},
            files={"file": ("missing.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["upload_id"]

        # Update video to READY but with non-existent HLS path
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY
        video.hls_path = "/nonexistent/path/index.m3u8"
        db_session.commit()

        response = client.get(f"/stream/{upload_id}/playlist.m3u8", headers=headers)
        assert response.status_code == 404
        assert "Stream playlist not available" in response.json()["detail"]

        # Cleanup
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    @patch("src.routers.videos.probe_video_duration", return_value=120.0)
    def test_stream_segment_success(self, mock_probe):
        """Test successful HLS segment streaming."""
        db_session = next(override_get_db())

        # Create user and video
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="segmentuser",
            email="segment@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "segmentuser", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Segment Test Video"},
            files={"file": ("segment.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["upload_id"]

        # Update video to READY and create HLS directory with segment
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        hls_dir = os.path.join("data", "hls", upload_id)
        os.makedirs(hls_dir, exist_ok=True)
        video.hls_path = os.path.join(hls_dir, "index.m3u8")

        # Create a fake segment file
        segment_path = os.path.join(hls_dir, "segment_000.ts")
        with open(segment_path, "wb") as f:
            f.write(b"fake segment data")

        db_session.commit()

        # Test segment streaming
        response = client.get(f"/stream/{upload_id}/segment_000.ts", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/MP2T"
        assert response.content == b"fake segment data"

        # Cleanup
        import shutil

        if os.path.exists(hls_dir):
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_stream_segment_invalid_name(self):
        """Test streaming segment with invalid segment name."""
        # Create and login test user
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="invalidseguser",
            email="invalidseg@example.com",
            hashed_password=hashed_password,
        )
        db_session = next(override_get_db())
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "invalidseguser", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test invalid segment name with path traversal
        response = client.get(
            "/stream/abcdefgh/../../../etc/passwd.ts", headers=headers
        )
        assert response.status_code == 404  # Video not found (path traversal prevented)

        # Test segment name without .ts extension
        response = client.get("/stream/abcdefgh/segment_000", headers=headers)
        assert response.status_code == 404  # Route not found (missing .ts extension)

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    @patch("src.routers.videos.probe_video_duration", return_value=120.0)
    def test_stream_segment_not_found(self, mock_probe):
        """Test streaming segment that doesn't exist."""
        db_session = next(override_get_db())

        # Create user and video
        from src.core.auth import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="segnotfound",
            email="segnotfound@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/auth/login", data={"username": "segnotfound", "password": "testpass"}
        )
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/videos/",
            data={"title": "Segment Not Found Video"},
            files={"file": ("segnot.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["upload_id"]

        # Update video to READY
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        hls_dir = os.path.join("data", "hls", upload_id)
        os.makedirs(hls_dir, exist_ok=True)
        video.hls_path = os.path.join(hls_dir, "index.m3u8")
        db_session.commit()

        # Try to stream non-existent segment
        response = client.get(f"/stream/{upload_id}/nonexistent.ts", headers=headers)
        assert response.status_code == 404
        assert "Stream segment not found" in response.json()["detail"]

        # Cleanup
        import shutil

        if os.path.exists(hls_dir):
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()
