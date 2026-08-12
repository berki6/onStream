"""Watch progress, share links, favorites."""

from datetime import datetime, timedelta, timezone

import pytest

from src.application import (
    favorites_service,
    share_link_service,
    watch_history_service,
)
from src.application.error_codes import ErrorCode
from src.application.errors import AppError
from src.infrastructure.db import models
from src.infrastructure.db.base import VideoStatus


@pytest.fixture
def ready_video(db_session, test_user):
    video = models.Video(
        upload_id="AbCdEfGh",
        user_id=test_user.id,
        title="Lab Clip Alpha",
        description="A searchable description about rivers",
        file_path="/tmp/x.mp4",
        status=VideoStatus.READY,
        duration=120.0,
        is_public=False,
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_watch_progress_continue_and_complete(db_session, test_user, ready_video):
    watch_history_service.upsert_progress(
        db_session, test_user.id, ready_video.upload_id, 40.0, 120.0
    )
    cont = watch_history_service.list_continue(db_session, test_user.id)
    assert len(cont) == 1
    assert cont[0]["upload_id"] == ready_video.upload_id
    assert cont[0]["position_seconds"] == 40.0

    watch_history_service.upsert_progress(
        db_session, test_user.id, ready_video.upload_id, 110.0, 120.0
    )
    cont2 = watch_history_service.list_continue(db_session, test_user.id)
    assert cont2 == []
    prog = watch_history_service.get_progress(
        db_session, test_user.id, ready_video.upload_id
    )
    assert prog["completed"] is True


def test_share_create_exchange_revoke(db_session, test_user, ready_video):
    created = share_link_service.create(
        db_session,
        test_user.id,
        ready_video.upload_id,
        expires_in_seconds=3600,
    )
    assert created["token"]
    assert "watch_url" in created
    assert created["app_url"].startswith("onstream://watch?")
    exchanged = share_link_service.exchange(
        db_session, created["public_id"], created["token"]
    )
    assert exchanged["playback_url"]
    assert exchanged["upload_id"] == ready_video.upload_id

    share_link_service.revoke(db_session, test_user.id, created["public_id"])
    with pytest.raises(AppError) as ei:
        share_link_service.exchange(
            db_session, created["public_id"], created["token"]
        )
    assert ei.value.code == ErrorCode.SHARE_REVOKED


def test_share_expired(db_session, test_user, ready_video):
    created = share_link_service.create(
        db_session,
        test_user.id,
        ready_video.upload_id,
        expires_in_seconds=60,
    )
    link = (
        db_session.query(models.ShareLink)
        .filter_by(public_id=created["public_id"])
        .one()
    )
    link.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    db_session.commit()
    with pytest.raises(AppError) as ei:
        share_link_service.exchange(
            db_session, created["public_id"], created["token"]
        )
    assert ei.value.code == ErrorCode.SHARE_EXPIRED


def test_share_view_limit(db_session, test_user, ready_video):
    created = share_link_service.create(
        db_session,
        test_user.id,
        ready_video.upload_id,
        expires_in_seconds=3600,
        max_views=1,
    )
    share_link_service.exchange(
        db_session, created["public_id"], created["token"]
    )
    with pytest.raises(AppError) as ei:
        share_link_service.exchange(
            db_session, created["public_id"], created["token"]
        )
    assert ei.value.code == ErrorCode.SHARE_VIEW_LIMIT


def test_favorites_toggle(db_session, test_user, ready_video):
    favorites_service.add(db_session, test_user.id, ready_video.upload_id)
    saved = favorites_service.list_saved(db_session, test_user.id)
    assert len(saved) == 1
    favorites_service.remove(db_session, test_user.id, ready_video.upload_id)
    assert favorites_service.list_saved(db_session, test_user.id) == []


def test_clear_progress_history_and_saved(db_session, test_user, ready_video):
    watch_history_service.upsert_progress(
        db_session, test_user.id, ready_video.upload_id, 40.0, 120.0
    )
    favorites_service.add(db_session, test_user.id, ready_video.upload_id)

    assert watch_history_service.list_continue(db_session, test_user.id)
    # Dismiss from Continue keeps History.
    dismissed = watch_history_service.dismiss_continue(
        db_session, test_user.id, ready_video.upload_id
    )
    assert dismissed["dismissed"] is True
    assert watch_history_service.list_continue(db_session, test_user.id) == []
    assert watch_history_service.list_history(db_session, test_user.id)

    # Watching again restores Continue.
    watch_history_service.upsert_progress(
        db_session, test_user.id, ready_video.upload_id, 45.0, 120.0
    )
    assert watch_history_service.list_continue(db_session, test_user.id)

    out = watch_history_service.delete_progress(
        db_session, test_user.id, ready_video.upload_id
    )
    assert out["cleared"] is True
    assert watch_history_service.list_history(db_session, test_user.id) == []

    watch_history_service.upsert_progress(
        db_session, test_user.id, ready_video.upload_id, 40.0, 120.0
    )
    cleared_cont = watch_history_service.clear_continue(db_session, test_user.id)
    assert cleared_cont["deleted"] >= 1
    assert watch_history_service.list_continue(db_session, test_user.id) == []
    assert watch_history_service.list_history(db_session, test_user.id)

    watch_history_service.upsert_progress(
        db_session, test_user.id, ready_video.upload_id, 110.0, 120.0
    )
    assert watch_history_service.list_continue(db_session, test_user.id) == []
    assert watch_history_service.list_history(db_session, test_user.id)

    cleared = watch_history_service.clear_history(db_session, test_user.id)
    assert cleared["deleted"] >= 1
    assert watch_history_service.list_history(db_session, test_user.id) == []

    cleared_saved = favorites_service.clear_saved(db_session, test_user.id)
    assert cleared_saved["deleted"] >= 1
    assert favorites_service.list_saved(db_session, test_user.id) == []


def test_keyword_search_ilike_fallback(db_session, test_user, ready_video):
    from src.application import search_service

    res = search_service.search(
        db_session, test_user.id, q="rivers", mode="keyword", limit=10
    )
    assert res["mode"] == "keyword"
    assert any(r["upload_id"] == ready_video.upload_id for r in res["results"])
