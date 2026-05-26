"""RSS fetcher — yields normalized entries from feeds.yaml."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import feedparser
import yaml

# Cap historical backlog. RSS feeds sort newest-first, so this takes the most
# recent N per feed. Hourly runs will pick up genuinely new items via URL dedup.
MAX_PER_FEED = 10


@dataclass
class LinkedContent:
    url: str
    text: str  # extracted body, capped


@dataclass
class Entry:
    category: str
    source: str
    title: str
    url: str
    published: str
    summary: str
    tags: list[str] = field(default_factory=list)
    linked_contents: list[LinkedContent] = field(default_factory=list)


def load_feeds(feeds_path: Path) -> dict:
    with feeds_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_all(feeds_path: Path, max_per_feed: int = MAX_PER_FEED) -> Iterator[Entry]:
    feeds = load_feeds(feeds_path)
    for category, sources in feeds.items():
        for src in sources:
            parsed = feedparser.parse(src["url"])
            for e in parsed.entries[:max_per_feed]:
                yield Entry(
                    category=category,
                    source=src["name"],
                    title=(e.get("title") or "").strip(),
                    url=e.get("link") or "",
                    published=e.get("published") or "",
                    summary=(e.get("summary") or "")[:500],
                )
