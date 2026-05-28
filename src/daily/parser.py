"""Parse daily/YYYY-MM-DD.md → per-candidate decisions.

Pulls candidate payloads from the trailing `<!-- candidates-data ... -->` JSONL
block, then walks the markdown to find each candidate's checkbox state.

A candidate with both `[x] ingest` and `[x] dismiss` is treated as a user
mistake and raises `DoubleCheckError` — the caller (process_daily) refuses to
proceed until the user fixes the file.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from src.daily.render import DATA_CLOSE, DATA_OPEN
from src.filter.scorer import ScoreResult
from src.sources.base import Candidate

_HEADER_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$", re.MULTILINE)
_INGEST_RE = re.compile(r"^- \[(x|X| )\] ingest\s*$", re.MULTILINE)
_DISMISS_RE = re.compile(r"^- \[(x|X| )\] dismiss\s*$", re.MULTILINE)


class Decision(str, Enum):
    ACCEPTED = "accepted"
    DISMISSED = "dismissed"
    PENDING = "pending"


@dataclass
class DailyEntry:
    slot: int
    candidate: Candidate
    score: ScoreResult
    decision: Decision


class DoubleCheckError(ValueError):
    """User checked both ingest and dismiss for the same candidate."""


def _extract_data_block(text: str) -> list[dict]:
    start = text.rfind(DATA_OPEN)
    if start == -1:
        return []
    end = text.find(DATA_CLOSE, start)
    if end == -1:
        return []
    raw = text[start + len(DATA_OPEN) : end].strip()
    items: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def _slot_sections(text: str) -> dict[int, str]:
    """Slice the body markdown into per-slot sections by `## N. ...` headers."""
    # Drop the data block before splitting so it doesn't leak into the last slot.
    body = text.split(DATA_OPEN, 1)[0]
    matches = list(_HEADER_RE.finditer(body))
    sections: dict[int, str] = {}
    for i, m in enumerate(matches):
        slot = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections[slot] = body[start:end]
    return sections


def _decision_for(section: str, *, slot: int) -> Decision:
    ingest_match = _INGEST_RE.search(section)
    dismiss_match = _DISMISS_RE.search(section)
    ingest = bool(ingest_match and ingest_match.group(1).lower() == "x")
    dismiss = bool(dismiss_match and dismiss_match.group(1).lower() == "x")
    if ingest and dismiss:
        raise DoubleCheckError(
            f"Slot {slot}: both ingest and dismiss checked. "
            f"Fix the daily file and retry."
        )
    if ingest:
        return Decision.ACCEPTED
    if dismiss:
        return Decision.DISMISSED
    return Decision.PENDING


def _rebuild_candidate(payload: dict) -> tuple[Candidate, ScoreResult]:
    score = ScoreResult(score=int(payload.pop("score", 0)), reason=str(payload.pop("reason", "")))
    payload.pop("slot", None)
    cand = Candidate(
        title=payload.get("title", ""),
        source=payload.get("source", ""),
        source_url=payload.get("source_url", ""),
        body=payload.get("body", ""),
        published=payload.get("published", ""),
        summary=payload.get("summary", ""),
        is_meta=bool(payload.get("is_meta", False)),
        original_url=payload.get("original_url"),
        extra_tags=list(payload.get("extra_tags", []) or []),
    )
    return cand, score


def parse_daily(path: Path) -> list[DailyEntry]:
    text = Path(path).read_text(encoding="utf-8")
    sections = _slot_sections(text)
    data_items = _extract_data_block(text)
    entries: list[DailyEntry] = []
    for item in data_items:
        slot = int(item.get("slot", 0))
        section = sections.get(slot)
        if section is None:
            # Data block claims a slot the markdown doesn't have — treat as pending.
            decision = Decision.PENDING
        else:
            decision = _decision_for(section, slot=slot)
        cand, score = _rebuild_candidate(dict(item))
        entries.append(
            DailyEntry(slot=slot, candidate=cand, score=score, decision=decision)
        )
    return entries
