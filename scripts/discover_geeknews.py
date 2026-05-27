"""Manually trigger GeekNews discovery.

Run: `uv run python scripts/discover_geeknews.py`
Options:
  --limit N     fetch first N entries from the feed (default: all up to source cap)
  --dry-run     score everything but don't write any raw file
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

    result = discover(geeknews.fetch, limit=args.limit, dry_run=args.dry_run)

    print(
        f"[geeknews] fetched={result.fetched} after_dedupe={result.after_dedupe} "
        f"scored={result.scored} passed={result.passed}"
    )
    for path in result.written_paths:
        print(f"  + {path}")
    if result.skipped:
        print("  skipped:")
        for title, score, reason in result.skipped:
            print(f"    - [{score}] {title[:60]}  | {reason[:80]}")
    if args.dry_run:
        print("(dry-run: no raw files written)")
    elif not result.written_paths:
        print("(no candidates passed score>=4 — nothing to ingest)")
    else:
        print(f"옵시디언에서 /ingest 로 {len(result.written_paths)}건 처리.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
