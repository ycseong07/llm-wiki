"""Render daily/YYYY-MM-DD.md from scored candidates.

The markdown is the human-facing surface — user toggles checkboxes in Obsidian.
A trailing HTML-comment JSONL block carries the full Candidate payload so
process_daily can write raw/articles without re-fetching.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from src.filter.scorer import ScoreResult
from src.sources.base import Candidate
from src.vault.paths import daily_dir, ensure_writable

DATA_OPEN = "<!-- candidates-data"
DATA_CLOSE = "-->"


def _candidate_block(slot: int, candidate: Candidate, score: ScoreResult) -> str:
    title = candidate.title.strip() or "(제목 없음)"
    parts = [
        f"## {slot}. {title}",
        "",
        "- [ ] ingest",
        "- [ ] dismiss",
        "",
        f"- url: {candidate.source_url}",
    ]
    if candidate.original_url:
        parts.append(f"- original_url: {candidate.original_url}")
    parts += [
        f"- score: {score.score}",
        f"- reason: {score.reason}",
        "",
        "### Summary",
        "",
        (candidate.summary.strip() or "_(요약 없음)_"),
        "",
    ]
    return "\n".join(parts)


def _data_block(items: list[tuple[int, Candidate, ScoreResult]]) -> str:
    lines = [DATA_OPEN]
    for slot, cand, score in items:
        payload = asdict(cand)
        payload["slot"] = slot
        payload["score"] = score.score
        payload["reason"] = score.reason
        lines.append(json.dumps(payload, ensure_ascii=False))
    lines.append(DATA_CLOSE)
    return "\n".join(lines)


def render_daily(
    items: list[tuple[Candidate, ScoreResult]],
    *,
    source: str,
    now: datetime,
) -> str:
    date_str = now.strftime("%Y-%m-%d")
    ts_str = now.strftime("%Y-%m-%d %H:%M %Z").strip()
    head = [
        f"# Daily / {date_str}",
        "",
        f"source: {source}",
        f"generated_at: {ts_str}",
        f"candidates: {len(items)}",
        "",
    ]
    if not items:
        head += [
            "_오늘은 임계값(score ≥ 4)을 통과한 후보가 없습니다. 자연스러운 가뭄._",
            "",
        ]
        return "\n".join(head)

    numbered = [(i + 1, c, s) for i, (c, s) in enumerate(items)]
    body = "\n".join(_candidate_block(slot, c, s) for slot, c, s in numbered)
    data = _data_block(numbered)
    return "\n".join(head) + body + "\n---\n\n" + data + "\n"


def daily_path_for(now: datetime) -> Path:
    return daily_dir() / f"{now.strftime('%Y-%m-%d')}.md"


def write_daily(text: str, *, now: datetime, overwrite: bool = False) -> Path:
    target = daily_path_for(now)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = ensure_writable(target)
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"Daily already exists: {target}. Delete it manually if you want to regenerate."
        )
    target.write_text(text, encoding="utf-8")
    return target
