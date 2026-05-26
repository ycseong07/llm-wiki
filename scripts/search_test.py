"""CLI search test.

Usage:
  uv run python scripts/search_test.py "LangGraph 활용 사례"
  uv run python scripts/search_test.py "AI 이미지 생성" --category ai --top 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.index.search import search  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="search query")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=20)
    parser.add_argument("--lambda", dest="mmr_lambda", type=float, default=0.5)
    parser.add_argument("--category", default=None, choices=["finance", "ai", "newsletter", "community", None])
    args = parser.parse_args()

    hits = search(
        args.query,
        top_n=args.top,
        candidate_k=args.candidates,
        mmr_lambda=args.mmr_lambda,
        category=args.category,
    )
    if not hits:
        print("(no hits)")
        return 0
    for i, h in enumerate(hits, 1):
        print(f"\n[{i}] score={h.score:.3f} category={h.category} source={h.source}")
        print(f"    {h.title}")
        snippet = h.chunk_text.replace("\n", " ")[:160]
        print(f"    {snippet}...")
        print(f"    {h.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
