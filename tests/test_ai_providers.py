"""AI provider registry tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.infrastructure.ai.captions.mock import MockCaptionsProvider
from src.infrastructure.ai.embeddings.mock import MockEmbeddingsProvider
from src.infrastructure.ai.moderation.heuristic import HeuristicModerationProvider
from src.infrastructure.ai.registry import (
    get_captions_provider,
    get_embeddings_provider,
    get_moderation_provider,
    reset_ai_providers,
)
from src.infrastructure.media.captions import transcribe
from src.infrastructure.media.embeddings import embed_texts


@pytest.fixture(autouse=True)
def _reset_ai():
    reset_ai_providers()
    yield
    reset_ai_providers()


def test_captions_registry_resolves_mock():
    provider = get_captions_provider("mock")
    assert isinstance(provider, MockCaptionsProvider)


def test_embeddings_registry_resolves_mock():
    provider = get_embeddings_provider("mock")
    assert isinstance(provider, MockEmbeddingsProvider)


def test_moderation_registry_resolves_heuristic():
    provider = get_moderation_provider("heuristic")
    assert isinstance(provider, HeuristicModerationProvider)


def test_mock_captions_output_stable(tmp_path: Path):
    # Missing media → mock uses default duration
    result = transcribe(str(tmp_path / "missing.wav"), provider="mock")
    assert result["language"] == "en"
    assert len(result["segments"]) >= 1
    assert all("start" in s and "end" in s and "text" in s for s in result["segments"])


def test_mock_embeddings_deterministic():
    a = embed_texts(["hello world"], provider="mock")
    b = embed_texts(["hello world"], provider="mock")
    assert a == b
    assert len(a) == 1
    assert len(a[0]) == 32
    # unit-ish vector
    norm = sum(x * x for x in a[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_unknown_captions_falls_back_non_prod(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.ai.registry.settings.ENV", "development"
    )
    monkeypatch.setattr(
        "src.infrastructure.ai.registry.settings.DEBUG", False
    )
    provider = get_captions_provider("does-not-exist")
    assert isinstance(provider, MockCaptionsProvider)


def test_unknown_captions_fails_closed_in_production(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.ai.policy.settings.ENV", "production"
    )
    monkeypatch.setattr(
        "src.infrastructure.ai.registry.settings.ENV", "production"
    )
    with pytest.raises(ValueError, match="Unknown captions provider"):
        get_captions_provider("does-not-exist")


def test_unknown_captions_fails_closed_even_with_debug(monkeypatch):
    monkeypatch.setattr("src.infrastructure.ai.policy.settings.ENV", "production")
    monkeypatch.setattr("src.infrastructure.ai.policy.settings.DEBUG", True)
    monkeypatch.setattr("src.infrastructure.ai.registry.settings.ENV", "production")
    monkeypatch.setattr("src.infrastructure.ai.registry.settings.DEBUG", True)
    with pytest.raises(ValueError, match="Unknown captions provider"):
        get_captions_provider("does-not-exist")


def test_moderation_heuristic_scores_clean_text():
    result = get_moderation_provider("heuristic").score(transcript_text="Hello world")
    assert "score" in result
    assert "labels" in result
    assert result["score"] >= 0.0
