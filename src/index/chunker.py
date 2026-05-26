"""Parse vault .md (frontmatter + body) and split body by Markdown headers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from langchain_text_splitters import MarkdownHeaderTextSplitter

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
]

_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=HEADERS_TO_SPLIT_ON,
    strip_headers=False,
)


@dataclass
class Chunk:
    text: str
    chunk_index: int
    frontmatter: dict
    vault_path: Path


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, parts[2].lstrip("\n")


def chunk_file(path: Path) -> list[Chunk]:
    raw = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(raw)
    if not body.strip():
        return []
    docs = _splitter.split_text(body)
    if not docs:
        return [Chunk(text=body.strip(), chunk_index=0, frontmatter=meta, vault_path=path)]
    return [
        Chunk(text=d.page_content, chunk_index=i, frontmatter=meta, vault_path=path)
        for i, d in enumerate(docs)
        if d.page_content.strip()
    ]
