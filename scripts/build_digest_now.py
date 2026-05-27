"""Manual digest build.

Run: `uv run python scripts/build_digest_now.py`
Override the default "yesterday 07:00 ~ today 07:00" window with --days N
(useful after bulk vault edits that change mtimes).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.digest.builder import build_digest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=None,
                        help="Use last N days as the window instead of the default 07:00 boundary")
    args = parser.parse_args()
    result = build_digest(window_days=args.days)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
