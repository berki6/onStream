"""Transcript chunking and text embeddings."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Optional, Sequence

from src.core.config import settings
from src.core.logger import get_logger

logger = get_logger(__name__)

_MOCK_DIM = 32


def chunk_transcript(
    segments: List[Dict[str, Any]],
    max_chars: int = 400,
) -> List[Dict[str, Any]]:
    """
    Chunk transcript segments into embedding units.

    Each chunk: {chunk_index, start_ms, end_ms, text}.
    """
    if not segments:
        return []

    chunks: List[Dict[str, Any]] = []
    buf_text: List[str] = []
    buf_start: Optional[float] = None
    buf_end: float = 0.0

    def flush():
        nonlocal buf_text, buf_start, buf_end
        if not buf_text or buf_start is None:
            return
        text = " ".join(buf_text).strip()
        if not text:
            buf_text = []
            return
        chunks.append(
            {
                "chunk_index": len(chunks),
                "start_ms": int(buf_start * 1000),
                "end_ms": int(buf_end * 1000),
                "text": text,
            }
        )
        buf_text = []
        buf_start = None

    for seg in segments:
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start))
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        if buf_start is None:
            buf_start = start
        candidate = (" ".join(buf_text + [text])).strip()
        if buf_text and len(candidate) > max_chars:
            flush()
            buf_start = start
            buf_text = [text]
            buf_end = end
        else:
            buf_text.append(text)
            buf_end = end

    flush()
    return chunks


def _mock_embed(text: str, dim: int = _MOCK_DIM) -> List[float]:
    """Deterministic hash-based unit vector for CI."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    # Expand digest if needed
    raw = digest
    while len(raw) < dim * 4:
        raw += hashlib.sha256(raw).digest()
    vals = []
    for i in range(dim):
        # signed byte -> float in [-1, 1]
        b = raw[i]
        vals.append((b / 127.5) - 1.0)
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]


def embed_texts(
    texts: Sequence[str],
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> List[List[float]]:
    """
    Embed texts. Mock provider returns deterministic unit vectors.
    Real provider uses sentence-transformers when installed.
    """
    provider = (provider or settings.AI_EMBEDDINGS_PROVIDER or "mock").lower()
    if not texts:
        return []

    if provider == "mock":
        return [_mock_embed(t) for t in texts]

    if provider == "sentence_transformers":
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore

            model = SentenceTransformer(model_name or settings.EMBEDDING_MODEL)
            vectors = model.encode(list(texts), normalize_embeddings=True)
            return [list(map(float, v)) for v in vectors]
        except Exception as e:
            logger.warning(f"sentence-transformers unavailable, using mock: {e}")
            return [_mock_embed(t) for t in texts]

    logger.warning(f"Unknown embeddings provider '{provider}', using mock")
    return [_mock_embed(t) for t in texts]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def embedding_to_json(vector: Sequence[float]) -> str:
    return json.dumps([float(v) for v in vector])


def embedding_from_json(raw: str) -> List[float]:
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [float(x) for x in data]
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return []
