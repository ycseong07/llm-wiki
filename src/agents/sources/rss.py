"""RSS fetcher — yields normalized entries from feeds.yaml."""
import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import feedparser
import yaml

# Cap historical backlog. RSS feeds sort newest-first, so this takes the most
# recent N per feed. Hourly runs will pick up genuinely new items via URL dedup.
MAX_PER_FEED = 10

# RSS <description>/<summary> often contains HTML (hada.io uses <ul><li>...).
# Strip it to plain text so the downstream summarizer doesn't see truncated tags
# and the vault file isn't garbage if summarization fails.
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")


def _clean_summary(text: str, max_chars: int = 3000) -> str:
    if not text:
        return ""
    s = _BR_RE.sub("\n", text)
    s = _TAG_RE.sub(" ", s)
    s = html.unescape(s)
    s = _WS_RE.sub(" ", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s[:max_chars]


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
                    summary=_clean_summary(e.get("summary") or ""),
                )
