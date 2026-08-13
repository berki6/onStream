"""Async storyboard/poster job for live archives."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from src.core.config import settings
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus
from src.worker.handlers.storyboard_handler import process_storyboard
from tests.conftest import TestingSessionLocal


def test_process_storyboard_sets_preview_paths(
    test_user, db_session: Session, tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "VIDEO_HLS_DIR", tmp_path / "hls")
    monkeypatch.setattr(
        "src.worker.handlers.storyboard_handler.Session",
        TestingSessionLocal,
    )
    dest = tmp_path / "hls" / "sbLive012"
    dest.mkdir(parents=True)
    playlist = dest / "index.m3u8"
    playlist.write_text(
        "#EXTM3U\n#EXTINF:2.0,\nseg0.ts\n",
        encoding="utf-8",
    )
    (dest / "seg0.ts").write_bytes(b"\x00" * 8)

    video = models.Video(
        upload_id="sbLive012",
        user_id=test_user.id,
        title="Live archive",
        file_path=str(playlist).replace("\\", "/"),
        hls_path=str(dest / "master.m3u8").replace("\\", "/"),
        status=VideoStatus.READY,
        source="live",
        visibility="private",
        is_public=False,
        duration=2.0,
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    storage = MagicMock()
    storage.ensure_local.return_value = playlist
    storage.put_file.return_value = None

    with patch(
        "src.infrastructure.storage.get_storage",
        return_value=storage,
    ):
        with patch(
            "src.worker.handlers.storyboard_handler.generate_storyboard",
            return_value=(
                "data/hls/sbLive012/storyboard.jpg",
                "data/hls/sbLive012/storyboard.vtt",
            ),
        ):
            with patch(
                "src.worker.handlers.storyboard_handler.generate_thumbnail",
                return_value="data/thumbnails/9.jpg",
            ):
                with patch(
                    "src.worker.handlers.storyboard_handler.job_queue"
                ) as jq:
                    process_storyboard("sbLive012")
                    jq.mark_job_completed.assert_called_once_with(
                        "sbLive012", job_type="storyboard"
                    )

    db_session.expire_all()
    got = (
        db_session.query(models.Video)
        .filter(models.Video.upload_id == "sbLive012")
        .one()
    )
    assert got.storyboard_path == "data/hls/sbLive012/storyboard.jpg"
    assert got.storyboard_vtt_path == "data/hls/sbLive012/storyboard.vtt"
    assert got.thumbnail_path == "data/thumbnails/9.jpg"
