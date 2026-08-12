"""Worker unit tests updated for ABR pipeline (Phase 2)."""

import pytest
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

from sqlalchemy.orm import sessionmaker

from src.infrastructure.media.ffmpeg import extract_concise_error
from src.infrastructure.media.thumbnail import generate_thumbnail
from src.worker.handlers.transcode_handler import process_video, update_job_progress
from src.infrastructure.db import models
from src.infrastructure.db.session import engine


class TestVideoWorker:
    def setup_method(self):
        models.Base.metadata.drop_all(bind=engine)
        models.Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)
        self.session = self.Session()
        # Ensure a user exists for FK
        if not self.session.query(models.User).filter_by(id=1).first():
            self.session.add(
                models.User(
                    id=1,
                    username="workeruser",
                    email="worker@example.com",
                    hashed_password="x",
                )
            )
            self.session.commit()

    def teardown_method(self):
        self.session.close()

    def test_extract_concise_error_with_stderr(self):
        stderr = "Error while opening encoder for output stream #0:0\n"
        result = extract_concise_error(stderr)
        assert "Error while opening encoder" in result

    def test_extract_concise_error_empty(self):
        assert extract_concise_error("") == "Unknown error (stderr is empty)"

    def test_extract_concise_error_no_keywords(self):
        stderr = "Some random output without error keywords\nAnother line"
        assert extract_concise_error(stderr) == "Some random output without error keywords"

    def test_extract_concise_error_max_length(self):
        long_error = "Error: " + "x" * 300
        assert len(extract_concise_error(long_error)) <= 250

    @patch("subprocess.run")
    @patch.object(Path, "exists")
    def test_generate_thumbnail_success(self, mock_exists, mock_run):
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "src.infrastructure.media.thumbnail.settings.VIDEO_THUMBNAIL_DIR",
                Path(temp_dir),
            ):
                result = generate_thumbnail("/fake/video.mp4", 123)
                assert result is not None
                assert "123.jpg" in result

    @patch.object(Path, "exists", return_value=False)
    def test_generate_thumbnail_file_not_found(self, mock_exists):
        assert generate_thumbnail("/missing.mp4", 1) is None

    def test_update_job_progress(self):
        job = models.VideoJob(upload_id="testprog1")
        self.session.add(job)
        self.session.commit()
        update_job_progress(self.session, job, 50, eta=120, message="Halfway done")
        self.session.refresh(job)
        assert job.progress == 50
        assert job.eta == 120
        assert job.message == "Halfway done"
        self.session.delete(job)
        self.session.commit()

    @patch("src.worker.handlers.transcode_handler.emit_video_event")
    @patch("src.worker.handlers.transcode_handler.job_queue")
    @patch(
        "src.worker.handlers.transcode_handler.generate_storyboard",
        return_value=(None, None),
    )
    @patch(
        "src.worker.handlers.transcode_handler.generate_thumbnail",
        return_value="data/thumbnails/1.jpg",
    )
    @patch("src.worker.handlers.transcode_handler.encode_rendition")
    @patch("src.worker.handlers.transcode_handler.write_master_playlist")
    @patch("src.worker.handlers.transcode_handler.probe_height", return_value=720)
    @patch("src.infrastructure.storage.get_storage")
    def test_process_video_success(
        self,
        mock_get_storage,
        mock_probe,
        mock_master,
        mock_encode,
        mock_thumb,
        mock_story,
        mock_queue,
        mock_emit,
    ):
        storage = MagicMock()
        local = Path("fake.mp4")
        storage.ensure_local.return_value = local
        mock_get_storage.return_value = storage

        with patch.object(Path, "stat", return_value=MagicMock(st_size=10_000_000)):
            with patch.object(Path, "mkdir"):
                upload_id = f"ok{uuid.uuid4().hex[:6]}"
                mock_master.return_value = Path(f"data/hls/{upload_id}/master.m3u8")

                video = models.Video(
                    upload_id=upload_id,
                    user_id=1,
                    title="Test Video",
                    file_path="data/uploads/x.mp4",
                    status=models.VideoStatus.PENDING,
                    duration=30.0,
                )
                self.session.add(video)
                job = models.VideoJob(upload_id=upload_id)
                self.session.add(job)
                self.session.commit()

                process_video(self.session, job)
                self.session.refresh(video)
                self.session.refresh(job)

                assert video.status == models.VideoStatus.READY
                assert job.progress == 100
                assert job.stage == "ready"
                mock_encode.assert_called()
                mock_emit.assert_called()

                self.session.delete(job)
                self.session.delete(video)
                self.session.commit()

    @patch("src.infrastructure.storage.get_storage")
    def test_process_video_file_not_found(self, mock_get_storage):
        storage = MagicMock()
        storage.ensure_local.side_effect = FileNotFoundError("missing")
        mock_get_storage.return_value = storage

        upload_id = f"miss{uuid.uuid4().hex[:4]}"
        video = models.Video(
            upload_id=upload_id,
            user_id=1,
            title="Missing",
            file_path="data/uploads/nope.mp4",
            status=models.VideoStatus.PENDING,
        )
        job = models.VideoJob(upload_id=upload_id)
        self.session.add(video)
        self.session.add(job)
        self.session.commit()

        with patch("src.worker.handlers.transcode_handler.emit_video_event"):
            process_video(self.session, job)

        self.session.refresh(video)
        self.session.refresh(job)
        assert video.status == models.VideoStatus.ERROR
        assert job.stage == "error"

        self.session.delete(job)
        self.session.delete(video)
        self.session.commit()

    def test_process_video_no_video_found(self):
        job = models.VideoJob(upload_id="novideo1")
        self.session.add(job)
        self.session.commit()
        process_video(self.session, job)
        self.session.refresh(job)
        assert job.stage == "error"
        self.session.delete(job)
        self.session.commit()
