"""One-shot: rewrite every vault .md file's `tags:` frontmatter through
vault_writer.sanitize_tag, so Obsidian no longer marks tags with spaces or
parentheses as invalid. No LLM call, just regex normalization.

Run once after the sanitize_tag rule changes:
  uv run python scripts/_sanitize_existing_tags.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from src.agents.nodes.vault_writer import sanitize_tag  # noqa: E402
from src.config import VAULT_PATH  # noqa: E402

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


def _format(meta: dict) -> str:
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


def main() -> int:
    files = [
        p for p in VAULT_PATH.rglob("*.md")
        if not p.name.startswith(".") and "00_Daily" not in p.parts
    ]
    changed = 0
    untouched = 0
    for path in files:
        raw = path.read_text(encoding="utf-8")
        meta, rest = _split(raw)
        tags = meta.get("tags") or []
        if not (isinstance(tags, list) and tags):
            untouched += 1
            continue
        cleaned = [s for s in (sanitize_tag(str(t)) for t in tags) if s]
        if [str(t) for t in tags] == cleaned:
            untouched += 1
            continue
        meta["tags"] = cleaned
        new_content = _format(meta) + rest.lstrip("\n")
        # Keep separation between frontmatter and body
        if not new_content.endswith("\n"):
            new_content += "\n"
        path.write_text(new_content, encoding="utf-8")
        changed += 1
        print(f"  ok: {path.name}\n      before: {tags}\n      after:  {cleaned}")

    print(f"\nDone. changed={changed}  untouched={untouched}  total={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
