import pytest
from sqlalchemy.orm import Session
from src.services import crud
from src.schema import models, schemas
from src.core.auth import get_password_hash


class TestCRUDOperations:
    """Test CRUD operations for all database entities."""

    def test_get_user_by_username(self, db_session):
        """Test getting user by username."""
        # Create test user
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="testuser_crud",
            email="testuser_crud@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()

        # Test retrieval
        found_user = crud.get_user_by_username(db_session, "testuser_crud")
        assert found_user is not None
        assert found_user.username == "testuser_crud"
        assert found_user.email == "testuser_crud@example.com"

        # Test non-existent user
        not_found = crud.get_user_by_username(db_session, "nonexistent")
        assert not_found is None

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_get_user_by_email(self, db_session):
        """Test getting user by email."""
        # Create test user
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="testuser_email",
            email="emailtest@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()

        # Test retrieval
        found_user = crud.get_user_by_email(db_session, "emailtest@example.com")
        assert found_user is not None
        assert found_user.username == "testuser_email"
        assert found_user.email == "emailtest@example.com"

        # Test non-existent email
        not_found = crud.get_user_by_email(db_session, "nonexistent@example.com")
        assert not_found is None

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_create_user(self, db_session):
        """Test user creation."""
        user_data = schemas.UserCreate(
            username="newuser_crud",
            email="newuser@example.com",
            password="SecurePass123!",
        )

        created_user = crud.create_user(db_session, user_data)

        assert created_user.username == "newuser_crud"
        assert created_user.email == "newuser@example.com"
        assert created_user.hashed_password != "securepass123"  # Should be hashed
        assert created_user.is_active is True

        # Verify in database
        db_user = crud.get_user_by_username(db_session, "newuser_crud")
        assert db_user is not None
        assert db_user.email == "newuser@example.com"

        # Cleanup
        db_session.delete(created_user)
        db_session.commit()

    def test_get_user(self, db_session):
        """Test getting user by ID."""
        # Create test user
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="testuser_get",
            email="gettest@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Test retrieval
        found_user = crud.get_user(db_session, user.id)
        assert found_user is not None
        assert found_user.id == user.id
        assert found_user.username == "testuser_get"

        # Test non-existent ID
        not_found = crud.get_user(db_session, 99999)
        assert not_found is None

        # Cleanup
        db_session.delete(user)
        db_session.commit()

    def test_create_video(self, db_session):
        """Test video creation."""
        # Create test user first
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="videouser",
            email="video@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create video
        video_data = schemas.VideoCreate(
            title="Test Video CRUD",
            description="A test video for CRUD operations",
            duration=120.5,
            file_path="test_path.mp4",
        )

        created_video = crud.create_video(db_session, video_data, user.id)

        assert created_video.title == "Test Video CRUD"
        assert created_video.description == "A test video for CRUD operations"
        assert created_video.duration == 120.5
        assert created_video.user_id == user.id
        assert created_video.status == models.VideoStatus.PENDING
        assert created_video.upload_id is not None
        assert len(created_video.upload_id) == 8  # Default length

        # Verify in database
        db_video = crud.get_video_by_upload_id(db_session, created_video.upload_id)
        assert db_video is not None
        assert db_video.title == "Test Video CRUD"

        # Cleanup
        db_session.delete(created_video)
        db_session.delete(user)
        db_session.commit()

    def test_get_video(self, db_session):
        """Test getting video by ID."""
        # Create test user and video
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="videogetuser",
            email="videoget@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        video = models.Video(
            upload_id="testget12",
            user_id=user.id,
            title="Get Test Video",
            file_path="test_path.mp4",
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        # Test retrieval
        found_video = crud.get_video(db_session, video.id)
        assert found_video is not None
        assert found_video.id == video.id
        assert found_video.title == "Get Test Video"

        # Test non-existent ID
        not_found = crud.get_video(db_session, 99999)
        assert not_found is None

        # Cleanup
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_get_video_by_upload_id(self, db_session):
        """Test getting video by upload ID."""
        # Create test user and video
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="uploadiduser",
            email="uploadid@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        video = models.Video(
            upload_id="testupload",
            user_id=user.id,
            title="Upload ID Test Video",
            file_path="test_path.mp4",
        )
        db_session.add(video)
        db_session.commit()

        # Test retrieval
        found_video = crud.get_video_by_upload_id(db_session, "testupload")
        assert found_video is not None
        assert found_video.upload_id == "testupload"
        assert found_video.title == "Upload ID Test Video"

        # Test non-existent upload ID
        not_found = crud.get_video_by_upload_id(db_session, "nonexistent")
        assert not_found is None

        # Cleanup
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_get_videos_by_user(self, db_session):
        """Test getting videos by user with pagination."""
        # Create test user
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="multividuser",
            email="multivid@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create multiple videos
        videos = []
        for i in range(5):
            video = models.Video(
                upload_id=f"testvid{i:02d}",
                user_id=user.id,
                title=f"Test Video {i}",
                file_path=f"test_path{i}.mp4",
            )
            db_session.add(video)
            videos.append(video)
        db_session.commit()

        # Test getting all videos
        user_videos, total_count = crud.get_videos_by_user(db_session, user.id)
        assert len(user_videos) == 5
        assert total_count == 5

        # Test pagination - limit 2
        paginated, _ = crud.get_videos_by_user(db_session, user.id, skip=0, limit=2)
        assert len(paginated) == 2

        # Test pagination - skip 2, limit 2
        paginated2, _ = crud.get_videos_by_user(db_session, user.id, skip=2, limit=2)
        assert len(paginated2) == 2
        assert paginated2[0].title == "Test Video 2"
        assert paginated2[1].title == "Test Video 3"

        # Test with another user (should return empty)
        other_user = models.User(
            username="otheruser",
            email="other@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        other_videos, _ = crud.get_videos_by_user(db_session, other_user.id)
        assert len(other_videos) == 0

        # Cleanup
        for video in videos:
            db_session.delete(video)
        db_session.delete(user)
        db_session.delete(other_user)
        db_session.commit()

    def test_delete_video_by_upload_id(self, db_session):
        """Test soft deleting video by upload ID."""
        # Create test user and video
        hashed_password = get_password_hash("testpass")
        user = models.User(
            username="deleteuser",
            email="delete@example.com",
            hashed_password=hashed_password,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        video = models.Video(
            upload_id="testdelete",
            user_id=user.id,
            title="Delete Test Video",
            file_path="test_path.mp4",
        )
        db_session.add(video)
        db_session.commit()

        # Test deletion
        deleted_video = crud.delete_video_by_upload_id(db_session, "testdelete")
        assert deleted_video is not None
        assert deleted_video.upload_id == "testdelete"
        assert deleted_video.status == models.VideoStatus.DELETED

        # Verify it's soft deleted (not returned by normal queries)
        found_video = crud.get_video_by_upload_id(db_session, "testdelete")
        assert found_video is None

        # But still exists in database with DELETED status
        raw_video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == "testdelete")
            .first()
        )
        assert raw_video is not None
        assert raw_video.status == models.VideoStatus.DELETED

        # Test deleting non-existent video
        not_deleted = crud.delete_video_by_upload_id(db_session, "nonexistent")
        assert not_deleted is None

        # Cleanup
        db_session.delete(video)
        db_session.delete(user)
        db_session.commit()

    def test_create_video_job(self, db_session):
        """Test video job creation."""
        job_data = schemas.VideoJobCreate(upload_id="testjob123")

        created_job = crud.create_video_job(db_session, job_data)

        assert created_job.upload_id == "testjob123"
        assert created_job.status == "processing"
        assert created_job.progress == 0
        assert created_job.eta == 0
        assert created_job.message is None

        # Verify in database
        db_job = crud.get_job_for_video(
            db_session,
            models.Video(
                upload_id="testjob123", user_id=1, title="dummy", file_path="dummy.mp4"
            ),
        )
        assert db_job is not None
        assert db_job.upload_id == "testjob123"

        # Cleanup
        db_session.delete(created_job)
        db_session.commit()

    def test_get_job_for_video(self, db_session):
        """Test getting job for video."""
        # Create a video job
        job = models.VideoJob(upload_id="testjobget")
        db_session.add(job)
        db_session.commit()

        # Create a dummy video object for testing
        video = models.Video(
            upload_id="testjobget", user_id=1, title="Test Video", file_path="test.mp4"
        )

        # Test retrieval
        found_job = crud.get_job_for_video(db_session, video)
        assert found_job is not None
        assert found_job.upload_id == "testjobget"

        # Test with non-existent job
        video_no_job = models.Video(
            upload_id="nojob", user_id=1, title="No Job Video", file_path="test.mp4"
        )
        not_found = crud.get_job_for_video(db_session, video_no_job)
        assert not_found is None

        # Cleanup
        db_session.delete(job)
        db_session.commit()
