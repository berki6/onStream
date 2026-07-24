"""Embeddings provider protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Sequence


class EmbeddingsProvider(ABC):
    @abstractmethod
    def embed_texts(
        self, texts: Sequence[str], model_name: Optional[str] = None
    ) -> List[List[float]]:
        ...
