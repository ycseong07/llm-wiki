"""Optionally re-process existing vault .md files through fulltext+summarize.

Run only when you want to upgrade older entries' bodies. Skipped by default
because RSS-fetched glimpses may be all you need; only newly-collected
entries automatically use fulltext after this change.

Usage:
  uv run python scripts/backfill_fulltext.py            # all files
  uv run python scripts/backfill_fulltext.py --category ai
  uv run python scripts/backfill_fulltext.py --since 2026-05-26
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from src.agents.nodes.fulltext import fetch_fulltext  # noqa: E402
from src.agents.nodes.summarizer import summarize_entry  # noqa: E402
from src.agents.sources.rss import Entry  # noqa: E402
from src.config import VAULT_PATH  # noqa: E402
from src.index.indexer import index_file  # noqa: E402

_FRONTMATTER_ORDER = ["source", "url", "category", "published"]


def _split(raw: str) -> tuple[dict, str]:
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        return yaml.safe_load(parts[1]) or {}, parts[2]
    except yaml.YAMLError:
        return {}, parts[2]


def _format_frontmatter(meta: dict) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for k in _FRONTMATTER_ORDER:
        if k in meta:
            lines.append(f"{k}: {meta[k]}")
            seen.add(k)
    for k, v in meta.items():
        if k in seen or k == "tags":
            continue
        lines.append(f"{k}: {v}")
    tags = meta.get("tags") or []
    if isinstance(tags, list) and tags:
        quoted = ", ".join(f"\"{t}\"" for t in tags)
        lines.append(f"tags: [{quoted}]")
    else:
        lines.append("tags: []")
    return "---\n" + "\n".join(lines) + "\n---\n"


def _strip_body(body: str) -> tuple[str, str]:
    """Return (title, summary_paragraphs) from existing markdown body."""
    title = ""
    summary_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("[원문]"):
            continue
        if line.strip():
            summary_lines.append(line)
    return title, "\n".join(summary_lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category")
    parser.add_argument("--since", help="YYYY-MM-DD (mtime cutoff)")
    args = parser.parse_args()

    cutoff = None
    if args.since:
        cutoff = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    files = [
        p
        for p in VAULT_PATH.rglob("*.md")
        if not p.name.startswith(".") and "00_Daily" not in p.parts
    ]
    print(f"Scanning {len(files)} files")

    upgraded = 0
    skipped = 0
    for path in files:
        raw = path.read_text(encoding="utf-8")
        meta, rest = _split(raw)
        if args.category and meta.get("category") != args.category:
            skipped += 1
            continue
        if cutoff:
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                skipped += 1
                continue
        url = meta.get("url", "")
        if not url or "mail.google.com" in url:
            skipped += 1
            continue

        title, existing_summary = _strip_body(rest.lstrip("\n"))
        entry = Entry(
            category=meta.get("category", ""),
            source=meta.get("source", ""),
            title=title,
            url=url,
            published=str(meta.get("published", "")),
            summary=existing_summary,
            tags=meta.get("tags") or [],
        )

        before = len(entry.summary)
        entry = fetch_fulltext(entry)
        if len(entry.summary) <= before:
            skipped += 1
            continue
        entry = summarize_entry(entry)

        # Rewrite file: keep frontmatter (with refreshed tags), update body.
        if isinstance(entry.tags, list) and entry.tags:
            meta["tags"] = entry.tags
        new_body = (
            _format_frontmatter(meta)
            + f"\n# {entry.title}\n\n"
            + f"{entry.summary}\n\n"
            + f"[원문]({entry.url})\n"
        )
        path.write_text(new_body, encoding="utf-8")
        index_file(path)
        upgraded += 1
        print(f"  ok: {path.name}  body chars: {before} -> {len(entry.summary)}")

    print(f"\nUpgraded {upgraded}, skipped {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
