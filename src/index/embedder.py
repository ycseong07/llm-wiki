"""bge-m3 dense embeddings.

Singleton model — first call downloads ~2.3GB to HF cache. Auto-picks CUDA if available.
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-m3"
VECTOR_SIZE = 1024  # bge-m3 dense vector dimension

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # device=None lets sentence-transformers auto-detect (cuda > mps > cpu).
        _model = SentenceTransformer(MODEL_NAME, device=None)
    return _model


def embed(texts: Sequence[str], batch_size: int = 16) -> np.ndarray:
    """Returns float32 array of shape (len(texts), VECTOR_SIZE)."""
    if not texts:
        return np.zeros((0, VECTOR_SIZE), dtype=np.float32)
    return _get_model().encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
    ).astype(np.float32)
