"""Smoke tests for Phase 1 discover pipeline.

No network, no real Gemini. Just verifies:
- raw write boundary is enforced (writes outside raw/articles/ raise)
- slugify handles 한글/특수문자
- normalize_url strips tracking params + trailing slash
- discover() end-to-end with mocked fetch + scorer produces a raw file
"""
from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pytest

from src.filter import dedupe, scorer
from src.pipeline import discover
from src.sources.base import Candidate


@pytest.fixture
def vault(tmp_path, monkeypatch):
    (tmp_path / "raw" / "articles").mkdir(parents=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "index.md").write_text("# Wiki Index\n- foo\n", encoding="utf-8")
    (tmp_path / "나의 핵심 맥락.md").write_text("AI 엔지니어. 깊이 우선.\n", encoding="utf-8")
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "GRAPH_REPORT.md").write_text(
        "## God Nodes\n1. LLM Evaluation\n", encoding="utf-8"
    )
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    # purge cached lookups
    from src.filter.profile import load_profile
    load_profile.cache_clear()
    dedupe.existing_urls.cache_clear()
    return tmp_path


def test_slugify_korean_and_special_chars():
    assert discover.slugify("LLM 평가의 맹점: 우리는?") == "LLM 평가의 맹점- 우리는"
    assert discover.slugify("a" * 100, max_len=10) == "aaaaaaaaaa"
    assert discover.slugify("   ") == "untitled"


def test_normalize_url_strips_tracking_and_trailing():
    a = dedupe.normalize_url("HTTPS://Example.COM/post/?utm_source=x&id=1#frag")
    b = dedupe.normalize_url("https://example.com/post?id=1")
    assert a == b == "https://example.com/post?id=1"


def test_boundary_guard_rejects_outside_writes(vault):
    bad = vault / "wiki" / "evil.md"
    with pytest.raises(ValueError, match="Refusing to write outside raw/articles"):
        discover._ensure_inside_raw_articles(bad)
    good = vault / "raw" / "articles" / "x.md"
    assert discover._ensure_inside_raw_articles(good) == good.resolve()


def test_discover_writes_raw_on_pass(vault, monkeypatch):
    fake = Candidate(
        title="테스트 — 깊이 있는 LLM 평가",
        source="geeknews",
        source_url="https://news.hada.io/topic?id=999",
        body="본문 내용 길게 " * 50,
        published="Wed, 28 May 2026 09:00:00 +0900",
        summary="짧은 요약",
        is_meta=True,
        original_url="https://example.dev/post/1",
    )
    monkeypatch.setattr(
        scorer, "score", lambda c, p: scorer.ScoreResult(score=5, reason="강한 매칭")
    )

    result = discover.discover(
        lambda: iter([fake]), now=datetime(2026, 5, 28, 10, 0, tzinfo=discover.KST)
    )

    assert result.passed == 1
    assert len(result.written_paths) == 1
    raw_dir = vault / "raw" / "articles"
    written = list(raw_dir.glob("*.md"))
    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    assert "ingested: false" in text
    assert "discover_score: 5" in text
    assert "AUTO-APPENDED" in text
    assert fake.original_url in text


def test_discover_skips_when_below_threshold(vault, monkeypatch):
    fake = Candidate(
        title="별 관련 없는 글",
        source="geeknews",
        source_url="https://news.hada.io/topic?id=888",
        body="내용",
    )
    monkeypatch.setattr(
        scorer, "score", lambda c, p: scorer.ScoreResult(score=2, reason="얕음")
    )
    result = discover.discover(lambda: iter([fake]))
    assert result.passed == 0
    assert result.written_paths == []
    assert len(result.skipped) == 1


def test_dedupe_filters_known_urls(vault):
    existing = (vault / "raw" / "articles" / "2026-05-27_existing.md")
    existing.write_text(
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
