"""Qdrant client + collection schema (PROJECT_PLAN §3, Phase 3).

Collection is created on first call. Local Qdrant binds to 127.0.0.1:6333
(CLAUDE.md §2.4); no API key in this deployment.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from src.index.embedder import VECTOR_SIZE

COLLECTION = "vault_chunks"
QDRANT_NAMESPACE = uuid.UUID("8c4f3a1e-9b7d-4f5e-8a2c-1d6e3f5b7a9c")  # static; for ID derivation

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        host = os.environ.get("QDRANT_HOST", "127.0.0.1")
        port = int(os.environ.get("QDRANT_PORT", "6333"))
        _client = QdrantClient(host=host, port=port)
    return _client


def ensure_collection() -> None:
    client = get_client()
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION in existing:
        return
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=qm.VectorParams(size=VECTOR_SIZE, distance=qm.Distance.COSINE),
    )


def chunk_id(vault_path: Path, chunk_index: int) -> str:
    """Deterministic UUID5 so re-indexing the same chunk overwrites, not duplicates."""
    return str(uuid.uuid5(QDRANT_NAMESPACE, f"{vault_path.as_posix()}::{chunk_index}"))


def upsert_chunks(points: list[qm.PointStruct]) -> None:
    if not points:
        return
    get_client().upsert(collection_name=COLLECTION, points=points)


def delete_by_vault_path(vault_path: Path) -> None:
    """Remove all chunks for a given file (used when a file is deleted/moved)."""
    get_client().delete(
        collection_name=COLLECTION,
        points_selector=qm.FilterSelector(
            filter=qm.Filter(
                must=[qm.FieldCondition(key="vault_path", match=qm.MatchValue(value=vault_path.as_posix()))]
            )
        ),
    )
