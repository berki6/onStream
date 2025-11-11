import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from sqlalchemy.orm import sessionmaker
from src.tasks.video_worker import (
    process_video,
    generate_thumbnail,
    extract_concise_error,
    update_job_progress,
    process_job,
)
from src.schema import models
from src.core.database import engine


class TestVideoWorker:
    """Test video processing worker functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.Session = sessionmaker(bind=engine)
        self.session = self.Session()

    def teardown_method(self):
        """Clean up test fixtures."""
        self.session.close()

    def test_extract_concise_error_with_stderr(self):
        """Test error message extraction from FFmpeg stderr."""
        stderr = """
ffmpeg version 4.4.2 Copyright (c) 2000-2021 the FFmpeg developers
  built with gcc 11.2.0 (GCC)
Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'input.mp4':
  Duration: 00:02:00.00, start: 0.000000, bitrate: 128 kb/s
    Stream #0:0(und): Video: h264 (avc1 / 0x31637661), yuv420p, 640x480, 25 fps, 25 t/b, 12800 kb/s, SAR 1:1 DAR 4:3
Output #0, mp4, to 'output.mp4':
  Stream #0:0: Video: h264, yuv420p, 640x480, q=2-31, 25 fps
Stream mapping:
  Stream #0:0 -> #0:0 (copy)
Error while opening encoder for output stream #0:0 - maybe incorrect parameters such as bit_rate, rate, width or height
"""
        result = extract_concise_error(stderr)
        assert "Error while opening encoder" in result
        assert len(result) < 250

    def test_extract_concise_error_empty(self):
        """Test error extraction with empty stderr."""
        result = extract_concise_error("")
        assert result == "Unknown error (stderr is empty)"

    def test_extract_concise_error_no_keywords(self):
        """Test error extraction when no error keywords found."""
        stderr = "Some random output without error keywords\nAnother line"
        result = extract_concise_error(stderr)
        assert result == "Some random output without error keywords"

    def test_extract_concise_error_max_length(self):
        """Test error extraction respects max length."""
        long_error = "Error: " + "x" * 300
        result = extract_concise_error(long_error)
        assert len(result) <= 250

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_generate_thumbnail_success(self, mock_exists, mock_run):
        """Test successful thumbnail generation."""
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the thumbnail path
            with patch("src.tasks.video_worker.THUMBNAIL_DIR", temp_dir):
                result = generate_thumbnail("/fake/video.mp4", 123)

                assert result is not None
                assert "123.jpg" in result
                mock_run.assert_called_once()

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_generate_thumbnail_failure(self, mock_exists, mock_run):
        """Test thumbnail generation failure."""
        mock_exists.return_value = True
        mock_run.side_effect = Exception("FFmpeg failed")

        result = generate_thumbnail("/fake/video.mp4", 123)
        assert result is None

    @patch("subprocess.run")
    @patch("os.path.exists")
    def test_generate_thumbnail_file_not_found(self, mock_exists, mock_run):
        """Test thumbnail generation when input file doesn't exist."""
        mock_exists.return_value = False

        result = generate_thumbnail("/nonexistent/video.mp4", 123)
        assert result is None
        mock_run.assert_not_called()

    def test_update_job_progress(self):
        """Test job progress update."""
        # Create a test job
        job = models.VideoJob(upload_id="testprogress")
        self.session.add(job)
        self.session.commit()

        # Update progress
        update_job_progress(self.session, job, 50, eta=120, message="Halfway done")

        # Refresh and check
        self.session.refresh(job)
        assert job.progress == 50
        assert job.eta == 120
        assert job.message == "Halfway done"

        # Cleanup
        self.session.delete(job)
        self.session.commit()

    @patch("src.tasks.video_worker.generate_thumbnail")
    @patch("subprocess.run")
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("os.path.normpath")
    def test_process_video_success(
        self, mock_normpath, mock_makedirs, mock_exists, mock_run, mock_thumbnail
    ):
        """Test successful video processing."""
        # Setup mocks
        mock_normpath.return_value = "/normalized/path.mp4"
        mock_exists.return_value = True
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        mock_thumbnail.return_value = "/thumbnail/path.jpg"

        # Create test video and job
        video = models.Video(
            upload_id="testprocess",
            user_id=1,
            title="Test Video",
            file_path="/original/path.mp4",
            status=models.VideoStatus.PENDING,
        )
        self.session.add(video)

        job = models.VideoJob(upload_id="testprocess")
        self.session.add(job)
        self.session.commit()

        # Process video
        process_video(self.session, job)

        # Refresh and check results
        self.session.refresh(video)
        self.session.refresh(job)

        assert video.status == models.VideoStatus.READY
        assert video.hls_path is not None
        assert video.thumbnail_path == "/thumbnail/path.jpg"
        assert job.status == "ready"
        assert job.progress == 100
        assert "Job completed successfully" in job.message

        # Cleanup
        self.session.delete(job)
        self.session.delete(video)
        self.session.commit()

    @patch("os.path.exists")
    def test_process_video_file_not_found(self, mock_exists):
        """Test video processing when input file doesn't exist."""
        mock_exists.return_value = False

        # Create test video and job
        video = models.Video(
            upload_id="testmissing",
            user_id=1,
            title="Missing Video",
            file_path="/nonexistent/path.mp4",
            status=models.VideoStatus.PENDING,
        )
        self.session.add(video)

        job = models.VideoJob(upload_id="testmissing")
        self.session.add(job)
        self.session.commit()

        # Process video
        process_video(self.session, job)

        # Refresh and check results
        self.session.refresh(video)
        self.session.refresh(job)

        assert video.status == models.VideoStatus.ERROR
        assert job.status == "error"
        assert "Input video file not found" in job.message

        # Cleanup
        self.session.delete(job)
        self.session.delete(video)
        self.session.commit()

    @patch("src.tasks.video_worker.generate_thumbnail")
    @patch("subprocess.run")
    @patch("os.path.exists")
    @patch("os.makedirs")
    @patch("os.path.normpath")
    def test_process_video_transcoding_failure(
        self, mock_normpath, mock_makedirs, mock_exists, mock_run, mock_thumbnail
    ):
        """Test video processing when transcoding fails."""
        # Setup mocks
        mock_normpath.return_value = "/normalized/path.mp4"
        mock_exists.return_value = True
        mock_thumbnail.return_value = "/thumbnail/path.jpg"

        # Mock FFmpeg failure
        mock_run.side_effect = Exception("Transcoding failed")

        # Create test video and job
        video = models.Video(
            upload_id="testfailtranscoding",
            user_id=1,
            title="Failing Video",
            file_path="/original/path.mp4",
            status=models.VideoStatus.PENDING,
        )
        self.session.add(video)

        job = models.VideoJob(upload_id="testfailtranscoding")
        self.session.add(job)
        self.session.commit()

        # Process video
        process_video(self.session, job)

        # Refresh and check results
        self.session.refresh(video)
        self.session.refresh(job)

        assert video.status == models.VideoStatus.ERROR
        assert job.status == "error"
        assert "Processing failed" in job.message

        # Cleanup
        self.session.delete(job)
        self.session.delete(video)
        self.session.commit()

    def test_process_video_no_video_found(self):
        """Test processing when video doesn't exist in database."""
        job = models.VideoJob(upload_id="nonexistent")
        self.session.add(job)
        self.session.commit()

        # Process video
        process_video(self.session, job)

        # Refresh and check results
        self.session.refresh(job)

        assert job.status == "error"
        assert "Video not found" in job.message

        # Cleanup
        self.session.delete(job)
        self.session.commit()

    @patch("src.tasks.video_worker.Session")
    @patch("src.tasks.video_worker.process_video")
    def test_process_job_success(self, mock_process, mock_session_class):
        """Test successful job processing."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        mock_job = MagicMock()
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_job

        # Process job
        process_job("testupload")

        # Verify job was processed
        mock_process.assert_called_once_with(mock_session, mock_job)
        mock_session.close.assert_called_once()

    @patch("src.tasks.video_worker.Session")
    def test_process_job_not_found(self, mock_session_class):
        """Test job processing when job is not found."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        # Process job
        with patch("src.tasks.video_worker.logger") as mock_logger:
            process_job("missingupload")

        # Verify error was logged
        mock_logger.error.assert_called_with("Job not found for upload_id: missingupload")
        mock_session.close.assert_called_once()
