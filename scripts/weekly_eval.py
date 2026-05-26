"""Run the weekly synthetic Q&A evaluation.

Usage: `uv run python scripts/weekly_eval.py [--n 50]`
Scheduled by scripts/register_weekly_eval_task.ps1 (Sundays 02:00).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.eval.synthetic import run_eval  # noqa: E402
from src.eval.tracing import flush  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50)
    args = parser.parse_args()
    result = run_eval(n=args.n)
    print("\n" + json.dumps(result, ensure_ascii=False, indent=2))
    flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
