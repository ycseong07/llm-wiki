"""Backfill vault files whose body is too short under the current pipeline.

Two modes selected by --min-chars:
  - Default (50): treat files with <50 char body as empty. If regen still
    produces nothing, DELETE them (they were never useful).
  - Larger threshold (e.g. 1500): re-run all "thin" files through the new
    summarizer prompt. Originals with real content are kept if regen fails;
    originals that were truly empty are deleted.

Usage:
  uv run python scripts/backfill_empty.py                       # empty only
  uv run python scripts/backfill_empty.py --min-chars 1500      # rewrite thin
  uv run python scripts/backfill_empty.py --category ai
  uv run python scripts/backfill_empty.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from src.agents.nodes.fulltext import fetch_fulltext  # noqa: E402
from src.agents.nodes.link_expander import expand_links  # noqa: E402
from src.agents.nodes.summarizer import unified_summarize  # noqa: E402
from src.agents.nodes.vault_writer import sanitize_tag  # noqa: E402
from src.agents.sources.rss import Entry  # noqa: E402
from src.config import VAULT_PATH  # noqa: E402
from src.index.indexer import index_file  # noqa: E402
from src.index.qdrant import delete_by_vault_path  # noqa: E402

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
        cleaned = [s for s in (sanitize_tag(str(t)) for t in tags) if s]
        if cleaned:
            quoted = ", ".join(f"\"{t}\"" for t in cleaned)
            lines.append(f"tags: [{quoted}]")
        else:
            lines.append("tags: []")
    else:
        lines.append("tags: []")
    return "---\n" + "\n".join(lines) + "\n---\n"


def _body_text(body: str) -> tuple[str, str]:
    """Return (title, content_without_title_and_link)."""
    title = ""
    content_lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("[원문]"):
            continue
        content_lines.append(line)
    content = "\n".join(content_lines).strip()
    return title, content


TRULY_EMPTY = 50  # below this we consider the original truly empty


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="Filter by category (ai, finance, ...)")
    parser.add_argument("--min-chars", type=int, default=TRULY_EMPTY,
                        help="Process files whose body content is shorter than this")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = [
        p
        for p in VAULT_PATH.rglob("*.md")
        if not p.name.startswith(".") and "00_Daily" not in p.parts
    ]

    candidates: list[tuple[Path, dict, str, int]] = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        meta, rest = _split(raw)
        if args.category and meta.get("category") != args.category:
            continue
        title, content = _body_text(rest.lstrip("\n"))
        if len(content) < args.min_chars:
            candidates.append((path, meta, title, len(content)))

    print(f"Found {len(candidates)} files with body < {args.min_chars} chars")
    if args.dry_run:
        for p, _, _, n in candidates[:20]:
            print(f"  {n:5d} chars  would process: {p.name}")
        if len(candidates) > 20:
            print(f"  ... and {len(candidates) - 20} more")
        return 0

    rewritten = 0
    deleted = 0
    kept = 0  # regen failed but original had real content -> leave alone
    skipped_no_url = 0
    for path, meta, title, orig_len in candidates:
        url = meta.get("url", "")
        if not url:
            skipped_no_url += 1
            continue

        entry = Entry(
            category=meta.get("category", ""),
            source=meta.get("source", ""),
            title=title or path.stem,
            url=url,
            published=str(meta.get("published", "")),
            summary="",
            tags=meta.get("tags") or [],
        )

        entry = fetch_fulltext(entry)
        entry = expand_links(entry)
        entry = unified_summarize(entry)

        if entry.summary.strip():
            if isinstance(entry.tags, list) and entry.tags:
                meta["tags"] = entry.tags
            new_body = (
                _format_frontmatter(meta)
                + f"\n# {entry.title}\n\n"
                + f"{entry.summary}\n\n"
                + f"[원문]({entry.url})\n"
            )
            path.write_text(new_body, encoding="utf-8")
            try:
                index_file(path)
            except Exception as e:
                print(f"  index warn ({path.name}): {e!r}")
            rewritten += 1
            print(f"  ok: {path.name}  ({orig_len} -> {len(entry.summary)} chars)")
        elif orig_len < TRULY_EMPTY:
            try:
                delete_by_vault_path(path)
            except Exception as e:
                print(f"  qdrant warn ({path.name}): {e!r}")
            path.unlink()
            deleted += 1
            print(f"  del: {path.name}")
        else:
            kept += 1
            print(f"  keep (regen empty, original has content): {path.name}")

    print(
        f"\nDone. rewritten={rewritten}  deleted={deleted}  kept={kept}  "
        f"skipped_no_url={skipped_no_url}  total={len(candidates)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
