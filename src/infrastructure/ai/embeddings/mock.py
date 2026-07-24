"""Mock embeddings provider."""

from __future__ import annotations

from typing import List, Optional, Sequence

from src.infrastructure.ai.embeddings.base import EmbeddingsProvider


class MockEmbeddingsProvider(EmbeddingsProvider):
    def embed_texts(
        self, texts: Sequence[str], model_name: Optional[str] = None
    ) -> List[List[float]]:
        from src.infrastructure.media.embeddings import _mock_embed

        return [_mock_embed(t) for t in texts]
