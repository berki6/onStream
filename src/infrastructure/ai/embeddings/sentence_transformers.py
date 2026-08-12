"""sentence-transformers embeddings provider."""

from __future__ import annotations

from typing import List, Optional, Sequence

from src.core.config import settings
from src.core.logger import get_logger
from src.infrastructure.ai.embeddings.base import EmbeddingsProvider
from src.infrastructure.ai.embeddings.mock import MockEmbeddingsProvider
from src.infrastructure.ai.policy import fail_closed

logger = get_logger(__name__)


class SentenceTransformersEmbeddingsProvider(EmbeddingsProvider):
    def embed_texts(
        self, texts: Sequence[str], model_name: Optional[str] = None
    ) -> List[List[float]]:
        if not texts:
            return []
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model = SentenceTransformer(model_name or settings.EMBEDDING_MODEL)
            vectors = model.encode(list(texts), normalize_embeddings=True)
            return [list(map(float, v)) for v in vectors]
        except Exception as e:
            if fail_closed():
                raise
            logger.warning("sentence-transformers unavailable, using mock: %s", e)
            return MockEmbeddingsProvider().embed_texts(texts, model_name)
