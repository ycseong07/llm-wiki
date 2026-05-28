"""discover() writes daily/ and never touches raw/articles/."""
from __future__ import annotations

from datetime import datetime

from src.filter import scorer
from src.pipeline import discover
from src.sources.base import Candidate


def _fake_candidate(i: int, title: str) -> Candidate:
    return Candidate(
        title=title,
        source="geeknews",
        source_url=f"https://news.hada.io/topic?id={i}",
        body="본문 " * 50,
        published="Wed, 28 May 2026 09:00:00 +0900",
        summary=f"요약 {i}",
        is_meta=True,
        original_url=f"https://example.dev/post/{i}",
    )


def test_discover_writes_daily_not_raw(vault, monkeypatch):
    fakes = [_fake_candidate(i, f"좋은 글 {i}") for i in range(3)]
    monkeypatch.setattr(
        scorer, "score", lambda c, p: scorer.ScoreResult(score=5, reason="강한 매칭")
    )
    result = discover.discover(
        lambda: iter(fakes),
        source_name="geeknews",
        now=datetime(2026, 5, 28, 10, 0, tzinfo=discover.KST),
    )
    assert result.candidates_written == 3
    assert result.daily_path is not None
    assert result.daily_path.exists()
    # raw must be untouched
    raw = vault / "raw" / "articles"
    assert list(raw.glob("*.md")) == []


def test_discover_caps_at_top_5(vault, monkeypatch):
    fakes = [_fake_candidate(i, f"글 {i}") for i in range(8)]
    monkeypatch.setattr(
        scorer, "score",
        lambda c, p: scorer.ScoreResult(score=5, reason="ok"),
    )
    result = discover.discover(
        lambda: iter(fakes),
        source_name="geeknews",
        now=datetime(2026, 5, 28, 10, 0, tzinfo=discover.KST),
    )
    assert result.passed == 8
    assert result.candidates_written == 5  # DAILY_CAP


def test_discover_skips_below_threshold(vault, monkeypatch):
    fake = _fake_candidate(1, "별 관련 없는 글")
    monkeypatch.setattr(
        scorer, "score", lambda c, p: scorer.ScoreResult(score=2, reason="얕음")
    )
    result = discover.discover(
        lambda: iter([fake]),
        source_name="geeknews",
        now=datetime(2026, 5, 28, 10, 0, tzinfo=discover.KST),
    )
    assert result.candidates_written == 0
    assert result.passed == 0
    assert len(result.skipped) == 1
    # daily file is still written but with 0 candidates (drought)
    assert result.daily_path is not None
    text = result.daily_path.read_text(encoding="utf-8")
    assert "임계값" in text


def test_discover_refuses_overwrite(vault, monkeypatch):
    fake = _fake_candidate(1, "x")
    monkeypatch.setattr(scorer, "score", lambda c, p: scorer.ScoreResult(score=5, reason="ok"))
    now = datetime(2026, 5, 28, 10, 0, tzinfo=discover.KST)
    discover.discover(lambda: iter([fake]), source_name="geeknews", now=now)

    # second run with the same date should refuse rather than clobber state
    import pytest
    with pytest.raises(FileExistsError):
        discover.discover(lambda: iter([fake]), source_name="geeknews", now=now)
