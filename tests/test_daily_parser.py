"""Daily markdown parser: checkbox states + ingest+dismiss collision."""
from __future__ import annotations

from datetime import datetime

import pytest

from src.daily.parser import Decision, DoubleCheckError, parse_daily
from src.daily.render import render_daily, write_daily
from src.filter.scorer import ScoreResult
from src.pipeline.discover import KST
from src.sources.base import Candidate


def _daily(vault, now):
    items = [
        (Candidate(title=f"글 {i}", source="geeknews",
                   source_url=f"https://news.hada.io/topic?id={i}",
                   body="b", summary="s", is_meta=True,
                   original_url=f"https://e.com/{i}"),
         ScoreResult(score=4, reason="ok"))
        for i in range(3)
    ]
    text = render_daily(items, source="geeknews", now=now)
    return write_daily(text, now=now)


def test_parse_returns_pending_when_unchecked(vault):
    path = _daily(vault, datetime(2026, 5, 28, 7, 0, tzinfo=KST))
    entries = parse_daily(path)
    assert len(entries) == 3
    assert all(e.decision == Decision.PENDING for e in entries)


def test_parse_reads_ingest_check(vault):
    now = datetime(2026, 5, 28, 7, 0, tzinfo=KST)
    path = _daily(vault, now)
    text = path.read_text(encoding="utf-8")
    text = text.replace("- [ ] ingest", "- [x] ingest", 1)
    path.write_text(text, encoding="utf-8")
    entries = parse_daily(path)
    assert entries[0].decision == Decision.ACCEPTED
    assert entries[1].decision == Decision.PENDING
    assert entries[2].decision == Decision.PENDING


def test_parse_reads_dismiss_check(vault):
    now = datetime(2026, 5, 28, 7, 0, tzinfo=KST)
    path = _daily(vault, now)
    text = path.read_text(encoding="utf-8")
    text = text.replace("- [ ] dismiss", "- [x] dismiss", 1)
    path.write_text(text, encoding="utf-8")
    entries = parse_daily(path)
    assert entries[0].decision == Decision.DISMISSED


def test_parse_rejects_double_check(vault):
    now = datetime(2026, 5, 28, 7, 0, tzinfo=KST)
    path = _daily(vault, now)
    text = path.read_text(encoding="utf-8")
    text = text.replace("- [ ] ingest", "- [x] ingest", 1)
    text = text.replace("- [ ] dismiss", "- [x] dismiss", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(DoubleCheckError):
        parse_daily(path)


def test_parse_recovers_candidate_payload(vault):
    now = datetime(2026, 5, 28, 7, 0, tzinfo=KST)
    path = _daily(vault, now)
    entries = parse_daily(path)
    assert entries[0].candidate.source == "geeknews"
    assert entries[0].candidate.source_url == "https://news.hada.io/topic?id=0"
    assert entries[0].candidate.is_meta is True
    assert entries[0].candidate.original_url == "https://e.com/0"
    assert entries[0].score.score == 4
