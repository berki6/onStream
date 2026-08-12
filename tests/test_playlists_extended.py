import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from src.main import app
from src.infrastructure.db.session import get_db
from src.infrastructure.db import models
from tests.conftest import override_get_db
import tempfile
import os

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


class TestPlaylistRouterExtended:
    """Extended tests for playlist router endpoints."""

    def test_create_playlist_missing_title(self, db_session):
        """Test creating playlist with missing title."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="missingtitle",
            email="missingtitle@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "missingtitle", "password": "Testpass123!"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post("/v1/playlists/", json={}, headers=headers)
        assert response.status_code == 422  # Validation error for missing title

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_create_playlist_title_too_long(self, db_session):
        """Test creating playlist with title exceeding max length."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="longplaylist",
            email="longplaylist@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "longplaylist", "password": "Testpass123!"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        long_title = "A" * 201  # Exceeds MAX_TITLE_LENGTH
        response = client.post(
            "/v1/playlists/", json={"name": long_title}, headers=headers
        )
        assert (
            response.status_code == 422
        )  # Pydantic validation error for exceeding max length
        errors = response.json()
        assert len(errors) > 0
        assert "String should have at most 100 characters" in str(errors)

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_create_playlist_duplicate_title(self, db_session):
        """Test creating playlist with duplicate title for same user."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="duplicate",
            email="duplicate@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "duplicate", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create first playlist
        response = client.post(
            "/v1/playlists/", json={"name": "My Playlist"}, headers=headers
        )
        assert response.status_code == 201

        # Try to create duplicate
        response = client.post(
            "/v1/playlists/", json={"name": "My Playlist"}, headers=headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["error"]["message"]

        # Cleanup
        playlists = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.user_id == user.id)
            .all()
        )
        for playlist in playlists:
            db_session.delete(playlist)
        db_session.delete(user)
        db_session.commit()

    def test_add_video_to_playlist_not_found(self, db_session):
        """Test adding video to non-existent playlist."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="addnotfound",
            email="addnotfound@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "addnotfound", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/v1/playlists/999/videos/abcdefgh/",
            json={"position": 1},
            headers=headers,
        )
        assert response.status_code == 404
        assert "Playlist not found" in response.json()["error"]["message"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_add_video_to_playlist_wrong_user(self, db_session):
        """Test adding video to playlist owned by another user."""
        # Create two users
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")

        user1 = models.User(
            username="playlistowner",
            email="playlistowner@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username="playliststealer",
            email="playliststealer@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login as user1 and create playlist
        response = client.post(
            "/v1/auth/login", data={"username": "playlistowner", "password": "testpass"}
        )
        token1 = response.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/v1/playlists/", json={"name": "Owner's Playlist"}, headers=headers1
        )
        playlist_id = response.json()["data"]["id"]

        # Login as user2 and try to add video to user1's playlist
        response = client.post(
            "/v1/auth/login", data={"username": "playliststealer", "password": "testpass"}
        )
        token2 = response.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/abcdefgh/",
            json={"position": 1},
            headers=headers2,
        )
        assert response.status_code == 403
        assert "Access denied" in response.json()["error"]["message"]

        # Cleanup
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user1)
        db_session.delete(user2)
        db_session.commit()

    def test_add_video_to_playlist_video_not_found(self, mocker, db_session):
        """Test adding non-existent video to playlist."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="videonotfound",
            email="videonotfound@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "videonotfound", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create playlist
        response = client.post(
            "/v1/playlists/", json={"name": "Test Playlist"}, headers=headers
        )
        playlist_id = response.json()["data"]["id"]

        # Try to add non-existent video
        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/abcdefgh/",
            json={"position": 1},
            headers=headers,
        )
        assert response.status_code == 404
        assert "Video not found" in response.json()["error"]["message"]

        # Cleanup
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user)
        db_session.commit()

    def test_add_video_to_playlist_video_wrong_user(self, mocker, db_session):
        """Test adding video owned by another user to playlist."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create two users
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")

        user1 = models.User(
            username="videoowner",
            email="videoowner@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username="playlistuser",
            email="playlistuser@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login as user1 and create video
        response = client.post(
            "/v1/auth/login", data={"username": "videoowner", "password": "testpass"}
        )
        token1 = response.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/v1/videos/",
            data={"title": "Owner's Video"},
            files={"file": ("owner.mp4", b"content", "video/mp4")},
            headers=headers1,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Login as user2 and create playlist
        response = client.post(
            "/v1/auth/login", data={"username": "playlistuser", "password": "testpass"}
        )
        token2 = response.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.post(
            "/v1/playlists/", json={"name": "User2 Playlist"}, headers=headers2
        )
        playlist_id = response.json()["data"]["id"]

        # Try to add user1's video to user2's playlist
        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/{upload_id}/",
            json={"position": 1},
            headers=headers2,
        )
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
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user1)
        db_session.delete(user2)
        db_session.commit()

    def test_add_video_to_playlist_duplicate_video(self, mocker, db_session):
        """Test adding same video twice to playlist."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="duplicatevideo",
            email="duplicatevideo@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "duplicatevideo", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create playlist
        response = client.post(
            "/v1/playlists/", json={"name": "Duplicate Test"}, headers=headers
        )
        playlist_id = response.json()["data"]["id"]

        # Create video
        response = client.post(
            "/v1/videos/",
            data={"title": "Test Video"},
            files={"file": ("test.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Add video to playlist first time
        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/{upload_id}/",
            json={"position": 1},
            headers=headers,
        )
        assert response.status_code == 201

        # Try to add same video again
        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/{upload_id}/",
            json={"position": 2},
            headers=headers,
        )
        assert response.status_code == 400
        assert "already in playlist" in response.json()["error"]["message"]

        # Cleanup
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        if video:
            db_session.delete(video)
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user)
        db_session.commit()

    def test_remove_video_from_playlist_not_in_playlist(self, mocker, db_session):
        """Test removing video that is not in the playlist."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="notplaylist",
            email="notplaylist@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "notplaylist", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create playlist
        response = client.post(
            "/v1/playlists/", json={"name": "Remove Test"}, headers=headers
        )
        playlist_id = response.json()["data"]["id"]

        # Create video
        response = client.post(
            "/v1/videos/",
            data={"title": "Test Video"},
            files={"file": ("test.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Try to remove video not in playlist
        response = client.delete(
            f"/v1/playlists/{playlist_id}/videos/{upload_id}/", headers=headers
        )
        assert response.status_code == 404
        assert "not in playlist" in response.json()["error"]["message"]

        # Cleanup
        video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == upload_id)
            .first()
        )
        if video:
            db_session.delete(video)
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user)
        db_session.commit()

    def test_list_playlist_videos_empty_playlist(self, db_session):
        """Test listing videos from empty playlist."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="emptyplaylist",
            email="emptyplaylist@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "emptyplaylist", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create playlist
        response = client.post(
            "/v1/playlists/", json={"name": "Empty Playlist"}, headers=headers
        )
        playlist_id = response.json()["data"]["id"]

        # List videos (should be empty)
        response = client.get(f"/v1/playlists/{playlist_id}/videos/", headers=headers)
        assert response.status_code == 200
        videos = response.json()["data"]
        assert videos == []

        # Cleanup
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user)
        db_session.commit()

    def test_playlist_pagination_edge_cases(self, db_session):
        """Test playlist listing with edge case pagination."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="playlistpaginate",
            email="playlistpaginate@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "playlistpaginate", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test negative skip
        response = client.get("/v1/playlists/?skip=-1", headers=headers)
        assert response.status_code == 400
        assert "must be non-negative" in response.json()["error"]["message"]

        # Test zero limit
        response = client.get("/v1/playlists/?limit=0", headers=headers)
        assert response.status_code == 400
        assert "must be between 1 and" in response.json()["error"]["message"]

        # Test negative limit
        response = client.get("/v1/playlists/?limit=-1", headers=headers)
        assert response.status_code == 400

        # Test limit exceeding maximum
        response = client.get("/v1/playlists/?limit=200", headers=headers)
        assert response.status_code == 400
        assert "must be between 1 and" in response.json()["error"]["message"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_delete_playlist_not_found(self, db_session):
        """Test deleting non-existent playlist."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

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
            "/v1/auth/login", data={"username": "deletenotfound", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.delete("/v1/playlists/999/", headers=headers)
        assert response.status_code == 404
        assert "Playlist not found" in response.json()["error"]["message"]

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_delete_playlist_wrong_user(self, db_session):
        """Test deleting playlist owned by another user."""
        # Create two users
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")

        user1 = models.User(
            username="playlistdeleteowner",
            email="playlistdeleteowner@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username="playlistdeletestealer",
            email="playlistdeletestealer@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login as user1 and create playlist
        response = client.post(
            "/v1/auth/login",
            data={"username": "playlistdeleteowner", "password": "testpass"},
        )
        token1 = response.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/v1/playlists/", json={"name": "Owner's Playlist"}, headers=headers1
        )
        playlist_id = response.json()["data"]["id"]

        # Login as user2 and try to delete
        response = client.post(
            "/v1/auth/login",
            data={"username": "playlistdeletestealer", "password": "testpass"},
        )
        token2 = response.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.delete(f"/v1/playlists/{playlist_id}/", headers=headers2)
        assert response.status_code == 403
        assert "Access denied" in response.json()["error"]["message"]

        # Cleanup
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user1)
        db_session.delete(user2)
        db_session.commit()

    def test_playlist_video_position_update(self, mocker, db_session):
        """Test updating video position in playlist."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="positionupdate",
            email="positionupdate@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "positionupdate", "password": "testpass"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create playlist
        response = client.post(
            "/v1/playlists/", json={"name": "Position Test"}, headers=headers
        )
        playlist_id = response.json()["data"]["id"]

        # Create two videos
        response = client.post(
            "/v1/videos/",
            data={"title": "Video 1"},
            files={"file": ("video1.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id1 = response.json()["data"]["upload_id"]

        response = client.post(
            "/v1/videos/",
            data={"title": "Video 2"},
            files={"file": ("video2.mp4", b"content", "video/mp4")},
            headers=headers,
        )
        upload_id2 = response.json()["data"]["upload_id"]

        # Add videos to playlist
        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/{upload_id1}/",
            json={"position": 1},
            headers=headers,
        )
        assert response.status_code == 201

        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/{upload_id2}/",
            json={"position": 2},
            headers=headers,
        )
        assert response.status_code == 201

        # Update position of first video
        response = client.put(
            f"/v1/playlists/{playlist_id}/videos/{upload_id1}/",
            json={"position": 3},
            headers=headers,
        )
        assert response.status_code == 200

        # Verify positions
        response = client.get(f"/v1/playlists/{playlist_id}/videos/", headers=headers)
        videos = response.json()["data"]
        assert len(videos) == 2
        # Positions should be updated accordingly

        # Cleanup
        videos = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id.in_([upload_id1, upload_id2]))
            .all()
        )
        for video in videos:
            db_session.delete(video)
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user)
        db_session.commit()

    def test_add_video_to_playlist_cross_user_playlist(self, mocker, db_session):
        """Test adding video to playlist owned by another user."""
        # Mock video duration probe
        mock_probe = mocker.patch("src.infrastructure.media.ffmpeg.probe_duration")
        mock_probe.return_value = 120.0

        # Create two users
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("Testpass123!")

        user1 = models.User(
            username="playlistowner2",
            email="playlistowner2@example.com",
            hashed_password=hashed_password,
        )
        user2 = models.User(
            username="videouploader2",
            email="videouploader2@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user1)
        db_session.refresh(user2)

        # Login as user1 and create playlist
        response = client.post(
            "/v1/auth/login",
            data={"username": "playlistowner2", "password": "Testpass123!"},
        )
        token1 = response.json()["data"]["access_token"]
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(
            "/v1/playlists/", json={"name": "Cross User Playlist"}, headers=headers1
        )
        playlist_id = response.json()["data"]["id"]

        # Login as user2 and create video
        response = client.post(
            "/v1/auth/login",
            data={"username": "videouploader2", "password": "Testpass123!"},
        )
        token2 = response.json()["data"]["access_token"]
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.post(
            "/v1/videos/",
            data={"title": "Cross User Video"},
            files={"file": ("cross.mp4", b"content", "video/mp4")},
            headers=headers2,
        )
        upload_id = response.json()["data"]["upload_id"]

        # Try to add user2's video to user1's playlist (should fail)
        response = client.post(
            f"/v1/playlists/{playlist_id}/videos/{upload_id}/",
            json={"position": 1},
            headers=headers2,
        )
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
        playlist = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.id == playlist_id)
            .first()
        )
        if playlist:
            db_session.delete(playlist)
        db_session.delete(user1)
        db_session.delete(user2)
        db_session.commit()

    def test_playlist_duplicate_name_creation(self, db_session):
        """Test creating playlist with duplicate name for same user."""
        # Create and login test user
        from src.core.security.passwords import get_password_hash

        hashed_password = get_password_hash("Testpass123!")
        user = models.User(
            username="dupname",
            email="dupname@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        response = client.post(
            "/v1/auth/login", data={"username": "dupname", "password": "Testpass123!"}
        )
        token = response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create first playlist
        response = client.post(
            "/v1/playlists/", json={"name": "Duplicate Name"}, headers=headers
        )
        assert response.status_code == 201

        # Try to create second playlist with same name
        response = client.post(
            "/v1/playlists/", json={"name": "Duplicate Name"}, headers=headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["error"]["message"]

        # Cleanup
        playlists = (
            db_session.query(models.Playlist)
            .filter(models.Playlist.user_id == user.id)
            .all()
        )
        for playlist in playlists:
            db_session.delete(playlist)
        db_session.delete(user)
        db_session.commit()
