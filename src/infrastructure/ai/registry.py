"""AI provider registries and accessors."""

from __future__ import annotations

from typing import Callable, Dict, Optional

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.ai.captions.base import CaptionsProvider
from src.infrastructure.ai.captions.faster_whisper import FasterWhisperCaptionsProvider
from src.infrastructure.ai.captions.mock import MockCaptionsProvider
from src.infrastructure.ai.embeddings.base import EmbeddingsProvider
from src.infrastructure.ai.embeddings.mock import MockEmbeddingsProvider
from src.infrastructure.ai.embeddings.sentence_transformers import (
    SentenceTransformersEmbeddingsProvider,
)
from src.infrastructure.ai.moderation.base import ModerationProvider
from src.infrastructure.ai.moderation.heuristic import HeuristicModerationProvider
from src.infrastructure.ai.policy import fail_closed

logger = get_logger(__name__)

CaptionsFactory = Callable[[], CaptionsProvider]
EmbeddingsFactory = Callable[[], EmbeddingsProvider]
ModerationFactory = Callable[[], ModerationProvider]

CAPTIONS_REGISTRY: Dict[str, CaptionsFactory] = {
    "mock": MockCaptionsProvider,
    "faster_whisper": FasterWhisperCaptionsProvider,
}

EMBEDDINGS_REGISTRY: Dict[str, EmbeddingsFactory] = {
    "mock": MockEmbeddingsProvider,
    "sentence_transformers": SentenceTransformersEmbeddingsProvider,
}

MODERATION_REGISTRY: Dict[str, ModerationFactory] = {
    "heuristic": HeuristicModerationProvider,
}

_captions: Optional[CaptionsProvider] = None
_embeddings: Optional[EmbeddingsProvider] = None
_moderation: Optional[ModerationProvider] = None


def _resolve(name: str, registry: Dict[str, Callable], kind: str):
    key = (name or "").lower().strip()
    factory = registry.get(key)
    if factory is None:
        known = ", ".join(sorted(registry))
        if fail_closed():
            raise ValueError(f"Unknown {kind} provider '{key}'. Expected: {known}")
        logger.warning(
            "Unknown %s provider '%s'; falling back (non-production). Expected: %s",
            kind,
            key,
            known,
        )
        if "mock" in registry:
            return registry["mock"]()
        if "heuristic" in registry:
            return registry["heuristic"]()
        raise ValueError(f"Unknown {kind} provider '{key}'. Expected: {known}")
    return factory()


def get_captions_provider(name: Optional[str] = None) -> CaptionsProvider:
    global _captions
    if name is not None:
        return _resolve(name, CAPTIONS_REGISTRY, "captions")
    if _captions is None:
        _captions = _resolve(
            settings.AI_CAPTIONS_PROVIDER, CAPTIONS_REGISTRY, "captions"
        )
    return _captions


def get_embeddings_provider(name: Optional[str] = None) -> EmbeddingsProvider:
    global _embeddings
    if name is not None:
        return _resolve(name, EMBEDDINGS_REGISTRY, "embeddings")
    if _embeddings is None:
        _embeddings = _resolve(
            settings.AI_EMBEDDINGS_PROVIDER, EMBEDDINGS_REGISTRY, "embeddings"
        )
    return _embeddings


def get_moderation_provider(name: Optional[str] = None) -> ModerationProvider:
    global _moderation
    if name is not None:
        return _resolve(name, MODERATION_REGISTRY, "moderation")
    if _moderation is None:
        _moderation = _resolve(
            settings.AI_MODERATION_PROVIDER, MODERATION_REGISTRY, "moderation"
        )
    return _moderation


def reset_ai_providers() -> None:
    global _captions, _embeddings, _moderation
    _captions = None
    _embeddings = None
    _moderation = None
