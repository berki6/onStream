import pytest
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from src.infrastructure.db import models
from src.infrastructure.db.models import Base


class TestDatabaseModels:
    """Test database models and their relationships."""

    @pytest.fixture(scope="class")
    def test_engine(self):
        """Create a test engine for model testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        yield engine
        Base.metadata.drop_all(bind=engine)

    @pytest.fixture
    def db_session(self, test_engine):
        """Create a test database session."""
        Session = sessionmaker(bind=test_engine)
        session = Session()
        yield session
        session.rollback()
        session.close()

    def test_user_model_creation(self, db_session):
        """Test User model creation and attributes."""
        user = models.User(
            username="testuser",
            email="test@example.com",
            hashed_password="hashedpass123",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.id is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.hashed_password == "hashedpass123"
        assert user.is_active is True
        assert user.created_at is not None
        # updated_at is only set on updates, not creation
        # assert user.updated_at is not None

        # Test __repr__
        repr_str = repr(user)
        assert "testuser" in repr_str
        assert str(user.id) in repr_str

    def test_user_unique_constraints(self, db_session):
        """Test User model unique constraints."""
        # Create first user
        user1 = models.User(
            username="uniqueuser",
            email="unique@example.com",
            hashed_password="pass1",
        )
        db_session.add(user1)
        db_session.commit()

        # Try to create user with same username
        user2 = models.User(
            username="uniqueuser",  # Same username
            email="different@example.com",
            hashed_password="pass2",
        )
        db_session.add(user2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

        db_session.rollback()

        # Try to create user with same email
        user3 = models.User(
            username="differentuser",
            email="unique@example.com",  # Same email
            hashed_password="pass3",
        )
        db_session.add(user3)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_video_model_creation(self, db_session):
        """Test Video model creation and attributes."""
        # Create user first
        user = models.User(
            username="videouser",
            email="video@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()

        video = models.Video(
            upload_id="testvid12",
            user_id=user.id,
            title="Test Video",
            description="A test video",
            duration=120.5,
            file_path="data/uploads/test.mp4",
            hls_path="data/hls/testvid12/index.m3u8",
            thumbnail_path="data/thumbnails/1.jpg",
            status=models.VideoStatus.PENDING,
            is_public=False,
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        assert video.id is not None
        assert video.upload_id == "testvid12"
        assert video.user_id == user.id
        assert video.title == "Test Video"
        assert video.description == "A test video"
        assert video.duration == 120.5
        assert video.file_path == "data/uploads/test.mp4"
        assert video.hls_path == "data/hls/testvid12/index.m3u8"
        assert video.thumbnail_path == "data/thumbnails/1.jpg"
        assert video.status == models.VideoStatus.PENDING
        assert video.is_public is False
        assert video.created_at is not None
        # updated_at is only set on updates, not creation
        # assert video.updated_at is not None

        # Test __repr__
        repr_str = repr(video)
        assert "Test Video" in repr_str
        assert str(video.id) in repr_str

    def test_video_upload_id_unique_constraint(self, db_session):
        """Test Video upload_id unique constraint."""
        # Create user
        user = models.User(
            username="uploaduser",
            email="upload@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()

        # Create first video
        video1 = models.Video(
            upload_id="uniqueupload",
            user_id=user.id,
            title="Video 1",
            file_path="/videos/1.mp4",
        )
        db_session.add(video1)
        db_session.commit()

        # Try to create video with same upload_id
        video2 = models.Video(
            upload_id="uniqueupload",  # Same upload_id
            user_id=user.id,
            title="Video 2",
            file_path="/videos/2.mp4",
        )
        db_session.add(video2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_video_status_enum_values(self, db_session):
        """Test VideoStatus enum values."""
        # Create user
        user = models.User(
            username="statususer",
            email="status@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()

        # Test all status values
        statuses = [
            models.VideoStatus.PENDING,
            models.VideoStatus.PROCESSING,
            models.VideoStatus.READY,
            models.VideoStatus.ERROR,
            models.VideoStatus.DELETED,
        ]

        videos = []
        for i, status in enumerate(statuses):
            video = models.Video(
                upload_id=f"status{i:02d}",
                user_id=user.id,
                title=f"Status {status.value}",
                file_path=f"/videos/status{i}.mp4",
                status=status,
            )
            db_session.add(video)
            videos.append(video)

        db_session.commit()

        # Verify all videos were created with correct statuses
        for i, expected_status in enumerate(statuses):
            assert videos[i].status == expected_status

    def test_video_job_model_creation(self, db_session):
        """Test VideoJob model creation and attributes."""
        job = models.VideoJob(
            upload_id="testjob123",
            status="processing",
            progress=25,
            eta=300,
            message="Transcoding in progress",
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.upload_id == "testjob123"
        assert job.status == "processing"
        assert job.progress == 25
        assert job.eta == 300
        assert job.message == "Transcoding in progress"
        assert job.created_at is not None
        # updated_at is only set on updates, not creation
        # assert job.updated_at is not None

        # Test __repr__
        repr_str = repr(job)
        assert "testjob123" in repr_str
        assert "25" in repr_str
        assert "25%" in repr_str

    def test_video_job_upload_id_primary_key(self, db_session):
        """Test VideoJob upload_id as primary key."""
        # Create first job
        job1 = models.VideoJob(
            upload_id="jobprimary",
            status="processing",
        )
        db_session.add(job1)
        db_session.commit()

        # Remove the persistent instance from the session to avoid identity conflicts
        db_session.expunge(job1)

        # Try to create job with same upload_id
        job2 = models.VideoJob(
            upload_id="jobprimary",  # Same upload_id
            status="ready",
        )
        db_session.add(job2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_user_video_relationship(self, db_session):
        """Test User-Video relationship."""
        user = models.User(
            username="reluser",
            email="rel@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()

        # Create videos for the user
        videos = []
        for i in range(3):
            video = models.Video(
                upload_id=f"relvid{i:02d}",
                user_id=user.id,
                title=f"Related Video {i}",
                file_path=f"/videos/rel{i}.mp4",
            )
            db_session.add(video)
            videos.append(video)

        db_session.commit()

        # Refresh user to load relationship
        db_session.refresh(user)

        # Test forward relationship (User.videos)
        assert len(user.videos) == 3
        for video in user.videos:
            assert video.user_id == user.id

        # Test reverse relationship (Video.owner)
        for video in videos:
            db_session.refresh(video)
            assert video.owner.id == user.id
            assert video.owner.username == "reluser"

    def test_video_view_model_creation(self, db_session):
        """Test VideoView model creation and relationships."""
        # Create user and video
        user = models.User(
            username="viewuser",
            email="view@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()  # Commit user first

        video = models.Video(
            upload_id="viewvideo",
            user_id=user.id,
            title="View Test Video",
            file_path="/videos/view.mp4",
        )
        db_session.add(video)
        db_session.commit()

        # Create video view
        view = models.VideoView(
            user_id=user.id,
            video_id=video.id,
            viewed_at=None,  # Should use default
            watch_time=45.5,
            device_info="Chrome on Windows",
        )
        db_session.add(view)
        db_session.commit()
        db_session.refresh(view)

        assert view.id is not None
        assert view.user_id == user.id
        assert view.video_id == video.id
        assert view.viewed_at is not None  # Should have default timestamp
        assert view.watch_time == 45.5
        assert view.device_info == "Chrome on Windows"

        # Test relationships
        assert view.viewer.id == user.id
        assert view.video.id == video.id

        # Test reverse relationships
        db_session.refresh(user)
        db_session.refresh(video)

        assert len(user.video_views) == 1
        assert len(video.views) == 1

    def test_playlist_models_creation(self, db_session):
        """Test Playlist and PlaylistVideo model creation."""
        # Create user
        user = models.User(
            username="playlistuser",
            email="playlist@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()

        # Create playlist
        playlist = models.Playlist(
            user_id=user.id,
            name="My Test Playlist",
            is_public=True,
        )
        db_session.add(playlist)
        db_session.commit()
        db_session.refresh(playlist)

        assert playlist.id is not None
        assert playlist.user_id == user.id
        assert playlist.name == "My Test Playlist"
        assert playlist.is_public is True
        assert playlist.created_at is not None

        # Test __repr__
        repr_str = repr(playlist)
        assert "My Test Playlist" in repr_str
        assert str(playlist.id) in repr_str

        # Create videos for the playlist
        videos = []
        for i in range(2):
            video = models.Video(
                upload_id=f"plvid{i:02d}",
                user_id=user.id,
                title=f"Playlist Video {i}",
                file_path=f"/videos/pl{i}.mp4",
            )
            db_session.add(video)
            videos.append(video)

        db_session.commit()

        # Create playlist-video relationships
        playlist_videos = []
        for i, video in enumerate(videos):
            pv = models.PlaylistVideo(
                playlist_id=playlist.id,
                video_id=video.id,
                position=i,
            )
            db_session.add(pv)
            playlist_videos.append(pv)

        db_session.commit()

        # Test relationships
        db_session.refresh(playlist)
        assert len(playlist.videos) == 2

        for pv in playlist.videos:
            assert pv.playlist_id == playlist.id
            assert pv.video_id in [v.id for v in videos]

        # Test reverse relationships
        for video in videos:
            db_session.refresh(video)
            # Video doesn't have direct relationship to playlists in this model

    def test_playlist_video_unique_constraint(self, db_session):
        """Test PlaylistVideo unique constraint on playlist_id + video_id."""
        # Create user, playlist, and video
        user = models.User(
            username="uniquepluser",
            email="uniquepl@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()  # Commit user first

        playlist = models.Playlist(
            user_id=user.id,
            name="Unique Test Playlist",
        )
        db_session.add(playlist)

        video = models.Video(
            upload_id="uniquevid",
            user_id=user.id,
            title="Unique Video",
            file_path="/videos/unique.mp4",
        )
        db_session.add(video)
        db_session.commit()

        # Create first playlist-video relationship
        pv1 = models.PlaylistVideo(
            playlist_id=playlist.id,
            video_id=video.id,
            position=0,
        )
        db_session.add(pv1)
        db_session.commit()

        # Try to create duplicate relationship
        pv2 = models.PlaylistVideo(
            playlist_id=playlist.id,  # Same playlist
            video_id=video.id,  # Same video
            position=1,
        )
        db_session.add(pv2)

        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()

    def test_model_defaults(self, db_session):
        """Test model default values."""
        # Test User defaults
        user = models.User(
            username="defaults",
            email="defaults@example.com",
            hashed_password="pass",
            # is_active should default to True
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        assert user.is_active is True

        # Test Video defaults
        video = models.Video(
            upload_id="defaults12",
            user_id=user.id,
            title="Defaults Video",
            file_path="/videos/defaults.mp4",
            # status should default to PENDING
            # is_public should default to False
        )
        db_session.add(video)
        db_session.commit()
        db_session.refresh(video)

        assert video.status == models.VideoStatus.PENDING
        assert video.is_public is False

        # Test VideoJob defaults
        job = models.VideoJob(
            upload_id="defaultsjob",
            # status/stage default to queued (Phase 2)
            # progress should default to 0
            # eta should default to 0
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)

        assert job.status in ("processing", "queued")
        assert job.progress == 0
        assert job.eta == 0

    def test_cascade_delete_user_videos(self, db_session):
        """Test cascade delete from User to Videos."""
        user = models.User(
            username="cascadeuser",
            email="cascade@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()

        # Create videos for the user
        videos = []
        for i in range(2):
            video = models.Video(
                upload_id=f"cascade{i:02d}",
                user_id=user.id,
                title=f"Cascade Video {i}",
                file_path=f"/videos/cascade{i}.mp4",
            )
            db_session.add(video)
            videos.append(video)

        db_session.commit()

        # Delete user
        db_session.delete(user)
        db_session.commit()

        # Check that videos were cascade deleted
        for video in videos:
            found = (
                db_session.query(models.Video)
                .filter(models.Video.id == video.id)
                .first()
            )
            assert found is None

    def test_index_usage(self, db_session):
        """Test that database indexes are properly defined."""
        # This is more of a schema test - we can check that the tables exist
        # and have the expected structure

        # Check that we can query with indexed fields efficiently
        user = models.User(
            username="indexuser",
            email="index@example.com",
            hashed_password="pass",
        )
        db_session.add(user)
        db_session.commit()

        video = models.Video(
            upload_id="indexvideo",
            user_id=user.id,
            title="Index Test Video",
            file_path="/videos/index.mp4",
            status=models.VideoStatus.READY,
        )
        db_session.add(video)
        db_session.commit()

        # Test indexed queries
        found_user = (
            db_session.query(models.User)
            .filter(models.User.username == "indexuser")
            .first()
        )
        assert found_user is not None

        found_video = (
            db_session.query(models.Video)
            .filter(models.Video.upload_id == "indexvideo")
            .first()
        )
        assert found_video is not None

        # Test compound index (user_id + status)
        status_videos = (
            db_session.query(models.Video)
            .filter(
                models.Video.user_id == user.id,
                models.Video.status == models.VideoStatus.READY,
            )
            .all()
        )
        assert len(status_videos) == 1
