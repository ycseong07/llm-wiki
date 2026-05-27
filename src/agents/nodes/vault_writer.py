"""Write Entry to Vault as Markdown with YAML frontmatter.

Idempotent: returns None when target file already exists.
"""
import re
from datetime import date
from pathlib import Path

from src.agents.sources.rss import Entry

# Vault subfolders per PROJECT_PLAN.md §5.
CATEGORY_DIRS = {
    "finance": "10_Finance",
    "ai": "20_AI",
    "newsletter": "30_Newsletters",
    "community": "40_HadaIO",
}

_UNSAFE = re.compile(r"[^\w가-힣\- ]+")

# Obsidian tags allow letters/digits/Korean/_/-//  — everything else
# (spaces, parentheses, &, etc.) makes the tag show as "유효하지 않은 태그".
_TAG_INVALID = re.compile(r"[^\w가-힣\-/]+")


def _slug(title: str, max_len: int = 60) -> str:
    s = _UNSAFE.sub("", title).strip().replace(" ", "_")
    return s[:max_len] or "untitled"


def sanitize_tag(raw: str) -> str:
    s = _TAG_INVALID.sub("-", raw.strip())
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s


def target_path(entry: Entry, vault_root: Path) -> Path:
    """Compute the Vault path for an entry without writing anything."""
    subdir = CATEGORY_DIRS.get(entry.category, entry.category)
    fname = f"{date.today().isoformat()}_{entry.source}_{_slug(entry.title)}.md"
    return vault_root / subdir / fname


def _format_tags(tags: list[str]) -> str:
    if not tags:
        return "tags: []"
    cleaned = [s for s in (sanitize_tag(t) for t in tags) if s]
    if not cleaned:
        return "tags: []"
    quoted = ", ".join(f"\"{t}\"" for t in cleaned)
    return f"tags: [{quoted}]"


def write_entry(entry: Entry, vault_root: Path) -> Path | None:
    if not entry.summary.strip():
        return None
    path = target_path(entry, vault_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return None

    body = (
        f"---\n"
        f"source: {entry.source}\n"
        f"url: {entry.url}\n"
        f"category: {entry.category}\n"
        f"published: {entry.published}\n"
        f"{_format_tags(entry.tags)}\n"
        f"---\n\n"
        f"# {entry.title}\n\n"
        f"{entry.summary}\n\n"
        f"[원문]({entry.url})\n"
    )
    path.write_text(body, encoding="utf-8")
    return path
