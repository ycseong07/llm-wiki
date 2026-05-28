"""Append-only decision log.

feedback/candidate_decisions.jsonl is the source of truth for what the user
accepted or dismissed. Idempotency: re-running process_daily on the same daily
must not duplicate entries — we de-dupe by (date, slot).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from src.vault.paths import ensure_writable, feedback_dir

DECISIONS_FILENAME = "candidate_decisions.jsonl"


def decisions_path() -> Path:
    return feedback_dir() / DECISIONS_FILENAME


def iter_decisions() -> Iterator[dict]:
    path = decisions_path()
    if not path.is_file():
        return iter(())
    return _iter_jsonl(path)


def _iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def existing_keys(date_str: str) -> set[tuple[str, int]]:
    """(date, slot) keys already recorded — used to skip duplicates on re-run."""
    keys: set[tuple[str, int]] = set()
    for entry in iter_decisions():
        if entry.get("date") != date_str:
            continue
        slot = entry.get("slot")
        if isinstance(slot, int):
            keys.add((date_str, slot))
    return keys


def append_decisions(entries: Iterable[dict]) -> int:
    """Append entries; returns count actually written.

    Each entry must include 'date' and 'slot' (used for dedupe). Adds
    'recorded_at' if missing.
    """
    target = decisions_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target = ensure_writable(target)

    new_lines: list[str] = []
    seen_in_batch: set[tuple[str, int]] = set()
    for entry in entries:
        date = entry.get("date")
        slot = entry.get("slot")
        if not isinstance(date, str) or not isinstance(slot, int):
            raise ValueError(f"Decision entry missing date/slot: {entry!r}")
        key = (date, slot)
        if key in seen_in_batch:
            continue
        if key in existing_keys(date):
            continue
        seen_in_batch.add(key)
        out = dict(entry)
        out.setdefault("recorded_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
        new_lines.append(json.dumps(out, ensure_ascii=False))
    if not new_lines:
        return 0
    with target.open("a", encoding="utf-8") as f:
        f.write("\n".join(new_lines) + "\n")
    return len(new_lines)


def all_decision_urls() -> set[str]:
    """Every URL ever decided on (accepted or dismissed) — used by dedupe."""
    out: set[str] = set()
    for entry in iter_decisions():
        for key in ("url", "original_url"):
            v = entry.get(key)
            if isinstance(v, str) and v:
                out.add(v)
    return out
