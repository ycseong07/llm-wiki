"""Manually trigger GeekNews discovery → write daily/YYYY-MM-DD.md.

Run: `uv run python scripts/discover_geeknews.py`
Options:
  --limit N     fetch first N entries from the feed (default: all up to source cap)
  --dry-run     score everything but don't write the daily file
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.discover import discover  # noqa: E402
from src.sources import geeknews  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    result = discover(
        geeknews.fetch,
        source_name=geeknews.name,
        limit=args.limit,
        dry_run=args.dry_run,
    )

    print(
        f"[geeknews] fetched={result.fetched} after_dedupe={result.after_dedupe} "
        f"scored={result.scored} passed={result.passed} -> daily candidates={result.candidates_written}"
    )
    if result.skipped:
        print("  skipped (score < 4):")
        for title, score, reason in result.skipped:
            print(f"    - [{score}] {title[:60]}  | {reason[:80]}")
    if args.dry_run:
        print("(dry-run: no daily file written)")
        return 0
    if result.daily_path:
        print(f"  + {result.daily_path}")
    if result.candidates_written == 0:
        print("(0 candidates passed score>=4 — natural drought)")
    else:
        print(
            f"옵시디언 daily에서 ingest/dismiss 체크 후 "
            f"`uv run python scripts/process_daily.py --today` 실행."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
