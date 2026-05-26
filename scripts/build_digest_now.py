"""Manual digest build.

Run: `uv run python scripts/build_digest_now.py`
Hourly scheduling is via Windows Task Scheduler (scripts/register_digest_task.ps1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.digest.builder import build_digest  # noqa: E402


def main() -> int:
    result = build_digest()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
