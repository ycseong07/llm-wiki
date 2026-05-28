"""URL normalization + dedupe across raw / daily / feedback."""
from __future__ import annotations

from src.filter import dedupe
from src.sources.base import Candidate


def test_normalize_url_strips_tracking_and_trailing():
    a = dedupe.normalize_url("HTTPS://Example.COM/post/?utm_source=x&id=1#frag")
    b = dedupe.normalize_url("https://example.com/post?id=1")
    assert a == b == "https://example.com/post?id=1"


def test_dedupe_filters_known_raw_urls(vault):
    (vault / "raw" / "articles" / "2026-05-27_existing.md").write_text(
        "---\ntitle: x\nsource: https://example.com/post?id=1\n---\nbody\n",
        encoding="utf-8",
    )
    dedupe.existing_urls.cache_clear()
    fresh = dedupe.filter_new([
        Candidate(title="dup", source="geeknews",
                  source_url="https://example.com/post/?utm_source=tw&id=1", body=""),
        Candidate(title="new", source="geeknews",
                  source_url="https://example.com/new", body=""),
    ])
    assert [c.title for c in fresh] == ["new"]


def test_dedupe_filters_urls_seen_in_past_daily(vault):
    daily_md = (
        "# Daily / 2026-05-27\n\n## 1. seen\n\n"
        "- [ ] ingest\n- [ ] dismiss\n\n- url: https://news.hada.io/topic?id=5\n\n"
        "<!-- candidates-data\n"
        '{"slot": 1, "title": "seen", "source": "geeknews", '
        '"source_url": "https://news.hada.io/topic?id=5", "body": "", '
        '"original_url": "https://example.com/seen", "summary": "", '
        '"published": "", "is_meta": true, "extra_tags": [], '
        '"score": 4, "reason": "x"}\n'
        "-->\n"
    )
    (vault / "daily" / "2026-05-27.md").write_text(daily_md, encoding="utf-8")
    dedupe.existing_urls.cache_clear()
    fresh = dedupe.filter_new([
        Candidate(title="dup-original", source="geeknews",
                  source_url="https://news.hada.io/topic?id=99",
                  original_url="https://example.com/seen", body=""),
        Candidate(title="dup-meta", source="geeknews",
                  source_url="https://news.hada.io/topic?id=5", body=""),
        Candidate(title="new", source="geeknews",
                  source_url="https://news.hada.io/topic?id=6", body=""),
    ])
    assert [c.title for c in fresh] == ["new"]


def test_dedupe_filters_urls_from_decisions_log(vault):
    decisions = (
        '{"date":"2026-05-27","slot":1,"decision":"dismissed",'
        '"url":"https://news.hada.io/topic?id=10",'
        '"original_url":"https://blog.example/post"}\n'
    )
    (vault / "feedback" / "candidate_decisions.jsonl").write_text(decisions, encoding="utf-8")
    dedupe.existing_urls.cache_clear()
    fresh = dedupe.filter_new([
        Candidate(title="dup", source="geeknews",
                  source_url="https://news.hada.io/topic?id=10", body=""),
        Candidate(title="new", source="geeknews",
                  source_url="https://news.hada.io/topic?id=11", body=""),
    ])
    assert [c.title for c in fresh] == ["new"]
