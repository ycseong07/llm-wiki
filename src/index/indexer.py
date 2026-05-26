"""Index vault .md files into Qdrant.

`index_file(path)` is the unit operation — called by reindex_all and (later) the watcher.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from qdrant_client.http import models as qm

from src.index.chunker import chunk_file
from src.index.embedder import embed
from src.index.qdrant import chunk_id, delete_by_vault_path, ensure_collection, upsert_chunks


def _payload(chunk_text: str, chunk_index: int, frontmatter: dict, vault_path: Path) -> dict:
    tags = frontmatter.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return {
        "vault_path": vault_path.as_posix(),
        "chunk_index": chunk_index,
        "chunk_text": chunk_text,
        "source": frontmatter.get("source", ""),
        "url": frontmatter.get("url", ""),
        "category": frontmatter.get("category", ""),
        "title": _extract_title(chunk_text, frontmatter),
        "published": str(frontmatter.get("published", "")),
        "tags": [str(t) for t in tags],
    }


def _extract_title(chunk_text: str, frontmatter: dict) -> str:
    for line in chunk_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return frontmatter.get("title", "")


def index_file(path: Path) -> int:
    """(Re)index a single .md file. Returns number of chunks upserted."""
    chunks = chunk_file(path)
    if not chunks:
        delete_by_vault_path(path)
        return 0

    texts = [c.text for c in chunks]
    vectors = embed(texts)
    points = [
        qm.PointStruct(
            id=chunk_id(c.vault_path, c.chunk_index),
            vector=vectors[i].tolist(),
            payload=_payload(c.text, c.chunk_index, c.frontmatter, c.vault_path),
        )
        for i, c in enumerate(chunks)
    ]
    upsert_chunks(points)
    return len(points)


def index_paths(paths: Iterable[Path]) -> tuple[int, int]:
    """Index many files. Returns (file_count, chunk_count)."""
    ensure_collection()
    files = 0
    chunks_total = 0
    for p in paths:
        n = index_file(p)
        files += 1
        chunks_total += n
    return files, chunks_total


def walk_vault(vault_root: Path) -> Iterable[Path]:
    return (p for p in vault_root.rglob("*.md") if not p.name.startswith("."))
