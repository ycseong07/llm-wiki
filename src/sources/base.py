"""Source adapter interface + Candidate model.

A SourceAdapter fetches candidates from one external source. Candidates flow
through dedupe -> score -> raw writer. Adapters never touch the vault.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol


@dataclass
class Candidate:
    title: str
    source: str                       # adapter name, e.g. "geeknews"
    source_url: str                   # URL the user clipped (may be a meta page)
    body: str                         # full body extracted from the original article
    published: str = ""               # RFC822 / ISO date string from feed, may be empty
    summary: str = ""                 # short summary from RSS, used only if body extraction fails
    is_meta: bool = False             # True if source_url is an aggregator page (hada.io etc.)
    original_url: str | None = None   # original article URL when is_meta
    extra_tags: list[str] = field(default_factory=list)


class SourceAdapter(Protocol):
    name: str

    def fetch(self) -> Iterator[Candidate]: ...
