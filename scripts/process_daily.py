"""Process a daily/ note: accepted → raw/articles, all decisions → feedback.

Run:
  uv run python scripts/process_daily.py --today
  uv run python scripts/process_daily.py --date 2026-05-28
  uv run python scripts/process_daily.py --path "C:/path/to/daily/2026-05-28.md"

Idempotent: re-running on the same daily produces no duplicate raw files and
no duplicate feedback entries.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date as date_cls
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.daily.parser import DoubleCheckError  # noqa: E402
from src.daily.render import daily_path_for  # noqa: E402
from src.pipeline.process import process_daily  # noqa: E402
from src.pipeline.discover import KST  # noqa: E402


def _resolve_path(args: argparse.Namespace) -> Path:
    if args.path:
        return Path(args.path)
    if args.today:
        return daily_path_for(datetime.now(KST))
    if args.date:
        d = date_cls.fromisoformat(args.date)
        return daily_path_for(datetime(d.year, d.month, d.day, tzinfo=KST))
    raise SystemExit("Specify --today, --date YYYY-MM-DD, or --path FILE")


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--today", action="store_true")
    g.add_argument("--date", help="YYYY-MM-DD")
    g.add_argument("--path", help="Explicit daily file path")
    args = ap.parse_args()

    path = _resolve_path(args)
    if not path.is_file():
        print(f"daily file not found: {path}", file=sys.stderr)
        return 1

    try:
        result = process_daily(path)
    except DoubleCheckError as e:
        print(f"[process_daily] {e}", file=sys.stderr)
        return 2

    print(
        f"[process_daily] {result.date}: accepted={result.accepted} "
        f"dismissed={result.dismissed} pending={result.pending}"
    )
    for p in result.raw_written:
        print(f"  + raw: {p}")
    for url in result.raw_skipped_existing:
        print(f"  · already in raw/articles, skipped: {url}")
    print(f"  feedback appended: {result.feedback_appended}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
