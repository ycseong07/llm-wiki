"""Vault write allow-list: daily/, feedback/, raw/articles/ only."""
from __future__ import annotations

import pytest

from src.vault.paths import ensure_writable


def test_allows_daily(vault):
    assert ensure_writable(vault / "daily" / "2026-05-28.md") == (
        vault / "daily" / "2026-05-28.md"
    ).resolve()


def test_allows_feedback(vault):
    assert ensure_writable(vault / "feedback" / "candidate_decisions.jsonl")
    assert ensure_writable(vault / "feedback" / "mac_references_inbox" / "in.jsonl")


def test_allows_raw_articles(vault):
    assert ensure_writable(vault / "raw" / "articles" / "2026-05-28_foo.md")


@pytest.mark.parametrize(
    "rel",
    [
        "wiki/index.md",
        "wiki/concepts/foo.md",
        "Output/note.md",
        "graphify-out/GRAPH_REPORT.md",
        "raw/notes/x.md",  # raw subfolder other than articles
        "evil.md",  # vault root
    ],
)
def test_rejects_outside(vault, rel):
    target = vault / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match="Refusing to write outside vault allow-list"):
        ensure_writable(target)
