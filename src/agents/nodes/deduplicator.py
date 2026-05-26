"""Dedupe entries by URL.

Karpathy 1.2 deviation note: PROJECT_PLAN.md §6 Phase 2 calls for MinHash
near-duplicate detection. Starting with URL-equality dedup because (a) it
catches the dominant case (same article re-fetched), (b) MinHash adds a
~10MB dep (datasketch) and a threshold to tune. Swap in MinHash when
cross-source near-dupes actually show up in the vault.
"""
from typing import Iterable, Iterator

from src.agents.sources.rss import Entry


def dedupe_by_url(entries: Iterable[Entry]) -> Iterator[Entry]:
    seen: set[str] = set()
    for e in entries:
        if not e.url or e.url in seen:
            continue
        seen.add(e.url)
        yield e
