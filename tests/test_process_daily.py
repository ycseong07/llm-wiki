"""process_daily: accepted-only writes to raw/articles, full audit to feedback."""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from src.daily.parser import DoubleCheckError
from src.daily.render import render_daily, write_daily
from src.feedback.store import decisions_path
from src.feedback.profile import profile_path
from src.filter.scorer import ScoreResult
from src.pipeline.discover import KST
from src.pipeline.process import process_daily
from src.sources.base import Candidate


def _seed_daily(vault, *, checks):
    """checks: list of ('ingest' | 'dismiss' | None) per slot."""
    now = datetime(2026, 5, 28, 7, 0, tzinfo=KST)
    items = [
        (Candidate(
            title=f"글 {i}", source="geeknews",
            source_url=f"https://news.hada.io/topic?id={i}",
            body=f"본문 {i}", summary=f"요약 {i}", is_meta=True,
            original_url=f"https://example.dev/{i}",
        ), ScoreResult(score=4, reason=f"이유 {i}"))
        for i in range(len(checks))
    ]
    text = render_daily(items, source="geeknews", now=now)
    path = write_daily(text, now=now)

    text = path.read_text(encoding="utf-8")
    # Toggle each slot's checkbox by replacing the Nth occurrence.
    for slot_idx, choice in enumerate(checks):
        if choice == "ingest":
            text = _replace_nth(text, "- [ ] ingest", "- [x] ingest", slot_idx)
        elif choice == "dismiss":
            text = _replace_nth(text, "- [ ] dismiss", "- [x] dismiss", slot_idx)
    path.write_text(text, encoding="utf-8")
    return path


def _replace_nth(text: str, old: str, new: str, n: int) -> str:
    parts = text.split(old)
    if n >= len(parts) - 1:
        return text
    return old.join(parts[: n + 1]) + new + old.join(parts[n + 1 :])


def test_accepted_only_written_to_raw(vault):
    path = _seed_daily(vault, checks=["ingest", "dismiss", None])
    result = process_daily(path)
    assert result.accepted == 1
    assert result.dismissed == 1
    assert result.pending == 1
    raw_files = list((vault / "raw" / "articles").glob("*.md"))
    assert len(raw_files) == 1
    body = raw_files[0].read_text(encoding="utf-8")
    assert "ingested: false" in body
    assert "글 0" in body
    # dismissed candidate must not leak into raw
    assert "글 1" not in body


def test_feedback_records_all_decided(vault):
    path = _seed_daily(vault, checks=["ingest", "dismiss", None])
    process_daily(path)
    lines = [
        json.loads(l) for l in decisions_path().read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    assert len(lines) == 2  # accepted + dismissed, not pending
    decisions = {e["slot"]: e["decision"] for e in lines}
    assert decisions == {1: "accepted", 2: "dismissed"}


def test_preference_profile_recomputed(vault):
    path = _seed_daily(vault, checks=["ingest", "dismiss", None])
    process_daily(path)
    profile = json.loads(profile_path().read_text(encoding="utf-8"))
    assert profile["accepted_domains"].get("example.dev") == 1
    assert profile["dismissed_domains"].get("example.dev") == 1


def test_double_check_blocks_processing(vault):
    path = _seed_daily(vault, checks=["ingest"])
    text = path.read_text(encoding="utf-8")
    text = text.replace("- [ ] dismiss", "- [x] dismiss", 1)
    path.write_text(text, encoding="utf-8")
    with pytest.raises(DoubleCheckError):
        process_daily(path)


def test_idempotent_on_rerun(vault):
    path = _seed_daily(vault, checks=["ingest", "dismiss", None])
    r1 = process_daily(path)
    r2 = process_daily(path)
    assert len(r1.raw_written) == 1
    assert len(r2.raw_written) == 0  # already exists
    assert r2.raw_skipped_existing  # noted as already-present
    # Feedback should not duplicate either.
    lines = [
        l for l in decisions_path().read_text(encoding="utf-8").splitlines() if l.strip()
    ]
    assert len(lines) == 2
    assert r2.feedback_appended == 0


def test_dry_dismissed_does_not_touch_raw(vault):
    path = _seed_daily(vault, checks=["dismiss", "dismiss"])
    result = process_daily(path)
    assert result.accepted == 0
    assert list((vault / "raw" / "articles").glob("*.md")) == []
