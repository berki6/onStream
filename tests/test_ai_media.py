"""AI media intelligence unit and integration tests (mock providers)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.config import settings
from src.infrastructure.db import models
from src.infrastructure.media.captions import segments_to_vtt
from src.infrastructure.media.chapters import chapters_from_segments
from src.infrastructure.media.embeddings import (
    cosine_similarity,
    embed_texts,
    embedding_from_json,
    embedding_to_json,
)
from src.infrastructure.media.moderation import combine_scores, score_transcript
from src.infrastructure.queue.job_queue import JobQueueService, _parse_payload
from src.main import app
from src.infrastructure.db.session import get_db
from tests.conftest import override_get_db

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def _force_mock_ai(monkeypatch):
    monkeypatch.setattr(settings, "AI_ENABLED", True)
    monkeypatch.setattr(settings, "AI_CAPTIONS_PROVIDER", "mock")
    monkeypatch.setattr(settings, "AI_EMBEDDINGS_PROVIDER", "mock")
    monkeypatch.setattr(settings, "AI_MODERATION_THRESHOLD", 0.7)
    monkeypatch.setattr(settings, "AI_CAPTIONS_ENABLED", True)
    monkeypatch.setattr(settings, "AI_CHAPTERS_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MODERATION_ENABLED", True)
    monkeypatch.setattr(settings, "AI_EMBEDDINGS_ENABLED", True)
    monkeypatch.setattr(settings, "AI_SMART_THUMBNAIL_ENABLED", True)


def _auth_token():
    response = client.post(
        "/v1/auth/login",
        data={"username": "testuser", "password": "testpass"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def _make_video(db_session: Session, user, **overrides):
    # upload_ids must avoid ambiguous chars (0/O/1/I/l) for public API validation
    video = models.Video(
        upload_id=overrides.pop("upload_id", "abcdEFGH"),
        user_id=user.id,
        title=overrides.pop("title", "Test Video"),
        description=overrides.pop("description", "A sample description"),
        file_path=overrides.pop("file_path", "data/uploads/abcdEFGH.mp4"),
        status=overrides.pop("status", models.VideoStatus.READY),
        is_public=overrides.pop("is_public", False),
        duration=overrides.pop("duration", 60.0),
    )
    for k, v in overrides.items():
        if hasattr(video, k):
            setattr(video, k, v)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_segments_to_vtt_unit():
    segments = [
        {"start": 0.0, "end": 1.5, "text": "Hello"},
        {"start": 1.5, "end": 3.0, "text": "World"},
    ]
    vtt = segments_to_vtt(segments)
    assert vtt.startswith("WEBVTT")
    assert "Hello" in vtt
    assert "World" in vtt
    assert "-->" in vtt


def test_chapters_from_segments_unit():
    segments = [
        {"start": 0, "end": 5, "text": "Intro"},
        {"start": 6, "end": 10, "text": "More intro"},
        {"start": 50, "end": 55, "text": "Main topic"},
        {"start": 56, "end": 60, "text": "Details"},
    ]
    chapters = chapters_from_segments(segments, min_gap=30)
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Intro"
    assert chapters[1]["title"] == "Main topic"
    assert chapters[0]["start"] == 0
    assert chapters[1]["start"] == 50


def test_moderation_threshold_quarantine(db_session: Session, test_user):
    """Flagged transcript scores at/above threshold quarantine the video."""
    video = _make_video(
        db_session,
        test_user,
        upload_id="modqabcd",
        title="violence and gore content",
        description="explicit nsfw material",
    )
    text = f"{video.title} {video.description}"
    t_score, t_labels = score_transcript(text)
    result = combine_scores(t_score, t_labels, 0.0, [])
    assert result["score"] >= settings.AI_MODERATION_THRESHOLD

    # Apply the same quarantine rules as moderation_handler
    video.status = models.VideoStatus.QUARANTINED
    video.is_public = False
    video.moderation_score = result["score"]
    video.moderation_labels = json.dumps(result["labels"])
    video.quarantined_at = datetime.now(timezone.utc)
    db_session.commit()
    db_session.refresh(video)

    assert video.status == models.VideoStatus.QUARANTINED
    assert video.is_public is False
    assert video.moderation_score >= 0.7
    assert video.quarantined_at is not None


def test_review_approve_restores_ready(db_session: Session, test_user):
    video = _make_video(
        db_session,
        test_user,
        upload_id="revwabcd",
        status=models.VideoStatus.QUARANTINED,
        is_public=False,
        quarantined_at=datetime.now(timezone.utc),
        moderation_score=0.9,
    )
    token = _auth_token()
    response = client.post(
        f"/v1/moderation/{video.upload_id}/review",
        json={"action": "approve", "make_public": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["status"] == "READY"
    assert data["is_public"] is True

    db_session.refresh(video)
    assert video.status == models.VideoStatus.READY
    assert video.is_public is True
    assert video.quarantined_at is None


def test_search_keyword_finds_video(db_session: Session, test_user):
    _make_video(
        db_session,
        test_user,
        upload_id="srchabcd",
        title="UniquePineapple Tutorial",
        description="learning stuff",
    )
    token = _auth_token()
    response = client.get(
        "/v1/search/?q=Pineapple&mode=keyword",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert any(r["upload_id"] == "srchabcd" for r in results)


def test_semantic_search_ranks_with_mock_embeddings(db_session: Session, test_user):
    from src.infrastructure.db.repositories import embedding_repository

    v1 = _make_video(
        db_session,
        test_user,
        upload_id="semaaaaa",
        title="Cats playing piano",
    )
    v2 = _make_video(
        db_session,
        test_user,
        upload_id="sembbbbb",
        title="Cooking pasta recipes",
    )

    texts = ["cats playing piano music", "cooking pasta recipes kitchen"]
    vectors = embed_texts(texts, provider="mock")
    embedding_repository.replace_chunks(
        db_session,
        v1.id,
        [{"chunk_index": 0, "start_ms": 0, "end_ms": 1000, "text": texts[0]}],
        [vectors[0]],
    )
    embedding_repository.replace_chunks(
        db_session,
        v2.id,
        [{"chunk_index": 0, "start_ms": 0, "end_ms": 1000, "text": texts[1]}],
        [vectors[1]],
    )

    token = _auth_token()
    response = client.get(
        "/v1/search/?q=cats%20piano&mode=semantic&limit=5",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    results = response.json()["data"]["results"]
    assert len(results) >= 1
    assert results[0]["upload_id"] == "semaaaaa"
    assert results[0]["score"] >= results[-1]["score"]


def test_queue_typed_enqueue_dequeue(db_session: Session):
    jq = JobQueueService()
    mock_redis = MagicMock()
    jq.redis_client = mock_redis
    mock_redis.lpush.return_value = 1

    assert jq.enqueue_job("upldabcd", db_session, job_type="captions") is True
    args = mock_redis.lpush.call_args[0]
    assert args[0] == "video_jobs_queue"
    payload = json.loads(args[1])
    assert payload == {"upload_id": "upldabcd", "job_type": "captions"}

    mock_redis.blpop.return_value = (
        "video_jobs_queue",
        args[1].encode("utf-8") if isinstance(args[1], str) else args[1],
    )
    job = jq.dequeue_job()
    assert job == {"upload_id": "upldabcd", "job_type": "captions"}

    assert _parse_payload("legacyab") == {
        "upload_id": "legacyab",
        "job_type": "transcode",
    }


def test_queue_duplicate_same_job_type(db_session: Session):
    from src.infrastructure.queue.redis_client import CircuitBreakerOpenException

    jq = JobQueueService()
    mock_redis = MagicMock()
    jq.redis_client = mock_redis
    mock_redis.lpush.side_effect = CircuitBreakerOpenException("open")

    assert jq.enqueue_job("duplabcd", db_session, job_type="moderation") is True
    assert jq.enqueue_job("duplabcd", db_session, job_type="moderation") is True
    assert jq.enqueue_job("duplabcd", db_session, job_type="captions") is True

    jobs = (
        db_session.query(models.QueuedJob)
        .filter_by(upload_id="duplabcd", status="pending")
        .all()
    )
    types = {j.job_type for j in jobs}
    assert types == {"moderation", "captions"}
    assert len(jobs) == 2

    for j in jobs:
        db_session.delete(j)
    db_session.commit()


def test_mock_embeddings_deterministic():
    a = embed_texts(["hello world"], provider="mock")[0]
    b = embed_texts(["hello world"], provider="mock")[0]
    c = embed_texts(["different"], provider="mock")[0]
    assert a == b
    assert cosine_similarity(a, b) == pytest.approx(1.0)
    assert cosine_similarity(a, c) < 1.0
    raw = embedding_to_json(a)
    assert embedding_from_json(raw) == a


def test_combine_scores_unit():
    result = combine_scores(0.8, ["violence"], 0.1, [])
    assert result["score"] >= 0.7
    assert "violence" in result["labels"]
    assert score_transcript("clean content")[0] == 0.0
