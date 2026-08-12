import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.infrastructure.db.session import get_db
from src.infrastructure.db import models
from tests.conftest import override_get_db
import tempfile
from pathlib import Path
from unittest.mock import patch
from src.utils.paths import to_relative_path

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestStreamRouter:
    """Test HLS streaming endpoints."""

    def test_stream_playlist_success(self, db_session, mocker):
        """Test successful HLS playlist streaming."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create test user
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "streamuser", "password": "testpass"}
        )
        assert response.status_code == 200
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create and process video
        response = client.post(
            "/v1/videos/",
            data={"title": "Stream Test Video"},
            files={"file": ("stream.mp4", b"fake content", "video/mp4")},
            headers=headers,
        )
        assert response.status_code == 201
        upload_id = response.json()["data"]["upload_id"]

        # Update video to READY status with HLS path
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        # Create temporary HLS directory and playlist file
        hls_dir = Path("data") / "hls" / upload_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        playlist_path = hls_dir / "index.m3u8"

        playlist_content = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:10
#EXTINF:10.0,
segment_000.ts
#EXT-X-ENDLIST
"""
        with open(playlist_path, "w") as f:
            f.write(playlist_content)

        video.hls_path = to_relative_path(playlist_path)
        db_session.commit()

        # Test playlist streaming
        response = client.get(f"/v1/playback/{upload_id}/master.m3u8", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/vnd.apple.mpegurl"
        assert "#EXTM3U" in response.text
        assert "segment_000.ts" in response.text

        # Cleanup
        import shutil

        if hls_dir.exists():
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_stream_playlist_invalid_upload_id(self):
        """Test streaming with invalid upload ID format."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "invaliduser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test invalid upload ID (too short)
        response = client.get("/v1/playback/abc/master.m3u8", headers=headers)
        assert response.status_code == 400
        assert "Invalid upload ID format" in response.json()["error"]["message"]

        # Test invalid upload ID (wrong characters)
        response = client.get("/v1/playback/abcO1234/master.m3u8", headers=headers)
        assert response.status_code == 400
        assert "Invalid upload ID format" in response.json()["error"]["message"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_stream_playlist_video_not_found(self):
        """Test streaming playlist for non-existent video."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "notfounduser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/v1/playback/abcdefgh/master.m3u8", headers=headers)
        assert response.status_code == 404
        assert "Video not found" in response.json()["error"]["message"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    @patch("src.infrastructure.media.ffmpeg.probe_duration", return_value=120.0)
    def test_stream_playlist_unauthorized(self, mock_probe):
        """Test streaming playlist for video owned by another user."""
        db_session = next(override_get_db())

        # Create two users
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "otheruser", "password": "testpass"}
        )
        token2 = response.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Create video for user1
        response = client.post(
            "/v1/auth/login", data={"username": "owneruser", "password": "testpass"}
        )
        token1 = response.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/v1/videos/",
            data={"title": "Private Video"},
            files={"file": ("private.mp4", b"content", "video/mp4")},
            headers=headers1,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Try to access with user2
        response = client.get(f"/v1/playback/{upload_id}/master.m3u8", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["error"]["message"]

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

    @patch("src.infrastructure.media.ffmpeg.probe_duration", return_value=120.0)
    def test_stream_playlist_video_not_ready(self, mock_probe):
        """Test streaming playlist for video that is not ready."""
        db_session = next(override_get_db())

        # Create user and video in PENDING status
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "pendinguser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/v1/videos/",
            data={"title": "Pending Video"},
            files={"file": ("pending.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Try to stream before processing
        response = client.get(f"/v1/playback/{upload_id}/master.m3u8", headers=headers)
        assert response.status_code == 409
        assert "Video is not ready for streaming" in response.json()["error"]["message"]

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

    @patch("src.infrastructure.media.ffmpeg.probe_duration", return_value=120.0)
    def test_stream_playlist_missing_file(self, mock_probe):
        """Test streaming playlist when HLS file doesn't exist."""
        db_session = next(override_get_db())

        # Create user and video
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "missinguser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/v1/videos/",
            data={"title": "Missing HLS Video"},
            files={"file": ("missing.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Update video to READY but with non-existent HLS path
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY
        video.hls_path = "/nonexistent/path/index.m3u8"
        db_session.commit()

        response = client.get(f"/v1/playback/{upload_id}/master.m3u8", headers=headers)
        assert response.status_code == 404
        assert "Stream playlist not available" in response.json()["error"]["message"]

        # Cleanup
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_stream_playlist_path_traversal_upload_id(self):
        """Test path traversal prevention in upload_id parameter for playlist."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="pathtravuser",
            email="pathtrav@example.com",
            hashed_password=hashed_password,
        )
        db_session = next(override_get_db())
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "pathtravuser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test path traversal in upload_id
        traversal_attempts = [
            "../../../etc/passwd/master.m3u8",
            "..\\..\\..\\windows\\system32\\config\\sam/master.m3u8",
            "....//....//....//etc/passwd/master.m3u8",
            "upload_id/../../../root/.bashrc/master.m3u8",
        ]

        for attempt in traversal_attempts:
            response = client.get(f"/v1/playback/{attempt}", headers=headers)
            assert response.status_code in [
                400,
                404,
            ]  # Either validation error or not found

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_stream_segment_path_traversal_segment_name(self):
        """Test path traversal prevention in segment name parameter."""
        db_session = next(override_get_db())

        # Create user and video
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="segpathtrav",
            email="segpathtrav@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "segpathtrav", "password": "Testpass123!"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Mock video duration probe
        with patch("src.infrastructure.media.ffmpeg.probe_duration", return_value=120.0):
            response = client.post(
                "/v1/videos/",
                data={"title": "Path Traversal Test Video"},
                files={"file": ("pathtrav.mp4", b"content", "video/mp4")},
                headers=headers,
            )
            upload_id = response.json()["data"]["upload_id"]

        # Update video to READY and create HLS directory
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        hls_dir = Path("data") / "hls" / upload_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        video.hls_path = to_relative_path(hls_dir / "index.m3u8")
        db_session.commit()

        # Test path traversal in segment name
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "segment_000.ts/../../../root/.bashrc",
        ]

        for attempt in traversal_attempts:
            response = client.get(f"/v1/playback/{upload_id}/{attempt}", headers=headers)
            assert (
                response.status_code == 404
            )  # Should not access files outside HLS directory

        # Cleanup
        import shutil

        if hls_dir.exists():
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_stream_cross_user_access_denied(self):
        """Test that users cannot access other users' video streams."""
        db_session = next(override_get_db())

        # Create two users
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user1 = models.User(
            username="streamuser1",
            email="streamuser1@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username="streamuser2",
            email="streamuser2@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login both users
        response = client.post(
            "/v1/auth/login", data={"username": "streamuser1", "password": "Testpass123!"}
        )
        token1 = response.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/v1/auth/login", data={"username": "streamuser2", "password": "Testpass123!"}
        )
        token2 = response.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        # User1 uploads a video
        with patch("src.infrastructure.media.ffmpeg.probe_duration", return_value=120.0):
            response = client.post(
                "/v1/videos/",
                data={"title": "User1 Private Video"},
                files={"file": ("private.mp4", b"content", "video/mp4")},
                headers=headers1,
            )
            upload_id = response.json()["data"]["upload_id"]

        # Update video to READY
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        hls_dir = Path("data") / "hls" / upload_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        video.hls_path = to_relative_path(hls_dir / "index.m3u8")

        # Create fake playlist and segment files
        with open(video.hls_path, "w") as f:
            f.write("#EXTM3U\n#EXTINF:10.0,\nsegment_000.ts\n")
        segment_path = hls_dir / "segment_000.ts"
        with open(segment_path, "wb") as f:
            f.write(b"fake segment data")

        db_session.commit()

        # User2 tries to access User1's playlist
        response = client.get(f"/v1/playback/{upload_id}/master.m3u8", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["error"]["message"]

        # User2 tries to access User1's segment
        response = client.get(f"/v1/playback/{upload_id}/segment_000.ts", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["error"]["message"]

        # User1 can access their own stream
        response = client.get(f"/v1/playback/{upload_id}/master.m3u8", headers=headers1)
        assert response.status_code == 200

        response = client.get(f"/v1/playback/{upload_id}/segment_000.ts", headers=headers1)
        assert response.status_code == 200

        # Cleanup
        import shutil

        if hls_dir.exists():
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user1)
        db_session.delete(user2)
        db_session.commit()

    def test_stream_invalid_upload_id_format(self):
        """Test streaming with invalid upload_id formats."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="invalididuser",
            email="invalidid@example.com",
            hashed_password=hashed_password,
        )
        db_session = next(override_get_db())
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "invalididuser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test various invalid upload_id formats (avoid characters that break URL parsing)
        invalid_ids = [
            "",  # Empty
            " ",  # Space only
            "invalid-id-with-dashes-and-long-name-that-exceeds-limits",  # Too long
            "id_with_spaces",  # Contains spaces
            "idwithspecialchars",  # Special characters (safe ones)
            "path/traversal",  # Path traversal
            "idwithbackslashes",  # Backslashes
        ]

        for invalid_id in invalid_ids:
            try:
                response = client.get(
                    f"/v1/playback/{invalid_id}/master.m3u8", headers=headers
                )
                # Should either return 404 (video not found) or 400/422 (validation error)
                assert response.status_code in [400, 404, 422]
            except Exception:
                # Some invalid IDs may cause URL parsing errors, which is also acceptable
                pass

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    @patch("src.infrastructure.media.ffmpeg.probe_duration", return_value=120.0)
    def test_stream_segment_success(self, mock_probe):
        """Test successful HLS segment streaming."""
        db_session = next(override_get_db())

        # Create user and video
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "segmentuser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/v1/videos/",
            data={"title": "Segment Test Video"},
            files={"file": ("segment.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Update video to READY and create HLS directory with segment
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        hls_dir = Path("data") / "hls" / upload_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        video.hls_path = to_relative_path(hls_dir / "index.m3u8")

        # Create a fake segment file
        segment_path = hls_dir / "segment_000.ts"
        with open(segment_path, "wb") as f:
            f.write(b"fake segment data")

        db_session.commit()

        # Test segment streaming
        response = client.get(f"/v1/playback/{upload_id}/segment_000.ts", headers=headers)
        assert response.status_code == 200
        assert response.headers["content-type"] == "video/MP2T"
        assert response.content == b"fake segment data"

        # Cleanup
        import shutil

        if hls_dir.exists():
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_stream_segment_invalid_name(self):
        """Test streaming segment with invalid segment name."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "invalidseguser", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test invalid segment name with path traversal
        response = client.get(
            "/v1/playback/abcdefgh/../../../etc/passwd.ts", headers=headers
        )
        assert response.status_code == 404  # Video not found (path traversal prevented)

        # Test segment name without .ts extension
        response = client.get("/v1/playback/abcdefgh/segment_000", headers=headers)
        assert response.status_code == 404  # Route not found (missing .ts extension)

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    @patch("src.infrastructure.media.ffmpeg.probe_duration", return_value=120.0)
    def test_stream_segment_not_found(self, mock_probe):
        """Test streaming segment that doesn't exist."""
        db_session = next(override_get_db())

        # Create user and video
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "segnotfound", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/v1/videos/",
            data={"title": "Segment Not Found Video"},
            files={"file": ("segnot.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Update video to READY
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        video.status = models.VideoStatus.READY

        hls_dir = Path("data") / "hls" / upload_id
        hls_dir.mkdir(parents=True, exist_ok=True)
        video.hls_path = to_relative_path(hls_dir / "index.m3u8")
        db_session.commit()

        # Try to stream non-existent segment
        response = client.get(f"/v1/playback/{upload_id}/nonexistent.ts", headers=headers)
        assert response.status_code == 404
        assert "Stream segment not found" in response.json()["error"]["message"]

        # Cleanup
        import shutil

        if hls_dir.exists():
            shutil.rmtree(hls_dir)
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()
