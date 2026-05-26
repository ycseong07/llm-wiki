"""Walk the vault and (re)index every .md into Qdrant.

Usage: `uv run python scripts/reindex_all.py`

Idempotent — re-running overwrites existing chunks (deterministic UUID5 IDs).
First run downloads bge-m3 (~2.3GB) to the HF cache.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import VAULT_PATH  # noqa: E402
from src.index.indexer import index_paths, walk_vault  # noqa: E402
from src.index.qdrant import COLLECTION, get_client  # noqa: E402


def main() -> int:
    print(f"Vault: {VAULT_PATH}")
    files = list(walk_vault(VAULT_PATH))
    print(f"Found {len(files)} .md files. Loading model + indexing...")

    t0 = time.monotonic()
    file_count, chunk_count = index_paths(files)
    elapsed = time.monotonic() - t0

    info = get_client().get_collection(COLLECTION)
    print(f"Indexed {file_count} files -> {chunk_count} chunks in {elapsed:.1f}s")
    print(f"Collection '{COLLECTION}' now has {info.points_count} points total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
