"""Run the full ingest pipeline once.

Usage: `uv run python scripts/ingest_now.py`
Hourly scheduling is via Windows Task Scheduler (Phase 2 next step).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.graph import build_graph  # noqa: E402
from src.config import VAULT_PATH  # noqa: E402


def main() -> int:
    print(f"Vault: {VAULT_PATH}")
    graph = build_graph()
    result = graph.invoke({"entries": []})
    print(f"Done. Written: {result.get('written', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
