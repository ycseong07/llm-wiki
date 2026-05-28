"""Allow-list write guard for the Obsidian vault.

Only three subtrees are writable by this project:
- daily/
- feedback/
- raw/articles/

Anything else (wiki/, Output/, graphify-out/, other raw subdirs, the vault root
itself) raises ValueError. Every code path that writes to the vault must go
through `ensure_writable(path)` first.
"""
from __future__ import annotations

from pathlib import Path

from src.config import obsidian_vault_path

ALLOWED_SUBPATHS: tuple[tuple[str, ...], ...] = (
    ("daily",),
    ("feedback",),
    ("raw", "articles"),
)


def _allowed_roots() -> list[Path]:
    vault = obsidian_vault_path()
    return [vault.joinpath(*parts).resolve() for parts in ALLOWED_SUBPATHS]


def ensure_writable(path: Path) -> Path:
    """Return the resolved path if it is strictly inside an allowed subtree.

    Strictly inside means the path is a proper descendant — writing the
    allow-list root itself is fine (a file directly under daily/ is OK), but
    writing to the vault root or any other subtree raises.
    """
    resolved = Path(path).resolve()
    for root in _allowed_roots():
        try:
            resolved.relative_to(root)
        except ValueError:
            continue
        return resolved
    raise ValueError(
        f"Refusing to write outside vault allow-list ({[p.name for p in _allowed_roots()]}): "
        f"{resolved}"
    )


def daily_dir() -> Path:
    return (obsidian_vault_path() / "daily").resolve()


def feedback_dir() -> Path:
    return (obsidian_vault_path() / "feedback").resolve()


def mac_inbox_dir() -> Path:
    return (feedback_dir() / "mac_references_inbox").resolve()


def raw_articles_dir() -> Path:
    return (obsidian_vault_path() / "raw" / "articles").resolve()
