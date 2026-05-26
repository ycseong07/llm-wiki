"""Offline tests for RSS pipeline. No network, no LLM, no Qdrant."""
from pathlib import Path

import feedparser

from src.agents.nodes.deduplicator import dedupe_by_url
from src.agents.nodes.vault_writer import write_entry
from src.agents.sources.rss import Entry

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Test</title>
<item><title>First</title><link>https://example.com/1</link><pubDate>2026-05-23</pubDate><description>summary one</description></item>
<item><title>Second</title><link>https://example.com/2</link><pubDate>2026-05-23</pubDate><description>summary two</description></item>
<item><title>Dup link</title><link>https://example.com/1</link><pubDate>2026-05-23</pubDate><description>same url</description></item>
</channel></rss>
"""


def _to_entries(rss_text: str, category: str = "ai", source: str = "Test") -> list[Entry]:
    parsed = feedparser.parse(rss_text)
    return [
        Entry(
            category=category,
            source=source,
            title=e.title,
            url=e.link,
            published=e.get("published", ""),
            summary=e.get("summary", ""),
        )
        for e in parsed.entries
    ]


def test_dedup_by_url_removes_duplicate_links():
    deduped = list(dedupe_by_url(_to_entries(SAMPLE_RSS)))
    urls = [e.url for e in deduped]
    assert urls == ["https://example.com/1", "https://example.com/2"]


def test_vault_writer_creates_markdown(tmp_path: Path):
    entry = _to_entries(SAMPLE_RSS)[0]
    path = write_entry(entry, tmp_path)
    assert path is not None
    content = path.read_text(encoding="utf-8")
    assert "url: https://example.com/1" in content
    assert "# First" in content
    assert "[원문](https://example.com/1)" in content


def test_vault_writer_is_idempotent(tmp_path: Path):
    entry = _to_entries(SAMPLE_RSS)[0]
    first = write_entry(entry, tmp_path)
    second = write_entry(entry, tmp_path)
    assert first is not None
    assert second is None
