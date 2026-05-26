"""Manual RSS ingest — fetch all feeds, dedupe by URL, write to Vault.

Run: uv run python scripts/ingest_rss_now.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.nodes.deduplicator import dedupe_by_url  # noqa: E402
from src.agents.nodes.vault_writer import write_entry  # noqa: E402
from src.agents.sources.rss import fetch_all  # noqa: E402
from src.config import VAULT_PATH  # noqa: E402

FEEDS = Path(__file__).resolve().parent.parent / "src" / "agents" / "sources" / "feeds.yaml"


def main() -> None:
    written = 0
    skipped = 0
    for entry in dedupe_by_url(fetch_all(FEEDS)):
        if write_entry(entry, VAULT_PATH) is not None:
            written += 1
        else:
            skipped += 1
    print(f"Vault: {VAULT_PATH}")
    print(f"Wrote {written} new files (skipped {skipped} existing).")


if __name__ == "__main__":
    main()
