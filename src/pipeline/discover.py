"""One discovery cycle: fetch -> dedupe -> score -> write daily/.

discover never writes to raw/articles/. Only process_daily does, after the
user checks ingest boxes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterator

from src.daily.render import render_daily, write_daily
from src.filter import dedupe, scorer
from src.filter.profile import load_profile
from src.sources.base import Candidate

KST = timezone(timedelta(hours=9))
DAILY_CAP = 5


@dataclass
class DiscoverResult:
    fetched: int
    after_dedupe: int
    scored: int
    passed: int
    daily_path: Path | None
    candidates_written: int
    skipped: list[tuple[str, int, str]]  # (title, score, reason)


def discover(
    source_fetch: Callable[[], Iterator[Candidate]],
    *,
    source_name: str,
    limit: int | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> DiscoverResult:
    now = now or datetime.now(KST)
    fetched = list(source_fetch())
    if limit is not None:
        fetched = fetched[:limit]
    fresh = dedupe.filter_new(fetched)

    profile = load_profile()
    passed: list[tuple[Candidate, scorer.ScoreResult]] = []
    skipped: list[tuple[str, int, str]] = []
    scored_count = 0

    for cand in fresh:
        result = scorer.score(cand, profile)
        scored_count += 1
        if scorer.passes(result):
            passed.append((cand, result))
        else:
            skipped.append((cand.title, result.score, result.reason))

    passed.sort(key=lambda x: x[1].score, reverse=True)
    top = passed[:DAILY_CAP]

    daily_path: Path | None = None
    if not dry_run:
        text = render_daily(top, source=source_name, now=now)
        daily_path = write_daily(text, now=now)

    return DiscoverResult(
        fetched=len(fetched),
        after_dedupe=len(fresh),
        scored=scored_count,
        passed=len(passed),
        daily_path=daily_path,
        candidates_written=len(top),
        skipped=skipped,
    )
