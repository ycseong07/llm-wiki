"""Process a daily/ note: write accepted candidates to raw/articles, log feedback.

This is the only path that writes to raw/articles/. discover writes only daily/.

Idempotent:
- Re-running on the same daily skips already-recorded decisions (by date+slot).
- Accepted candidates whose URL already exists in raw/articles/ are not
  re-written (matched via dedupe.normalize_url over frontmatter).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.daily.parser import DailyEntry, Decision, parse_daily
from src.feedback import profile as feedback_profile
from src.feedback.store import append_decisions
from src.filter import dedupe
from src.filter.scorer import SCORE_THRESHOLD, ScoreResult
from src.sources.base import Candidate
from src.vault.paths import ensure_writable, raw_articles_dir

_INVALID_FS = '<>:"/\\|?*'


@dataclass
class ProcessResult:
    daily_path: Path
    date: str
    accepted: int
    dismissed: int
    pending: int
    raw_written: list[Path]
    raw_skipped_existing: list[str]  # URLs already in raw
    feedback_appended: int


def _slugify(title: str, max_len: int = 60) -> str:
    s = title.strip()
    for ch in _INVALID_FS:
        s = s.replace(ch, "-")
    s = re.sub(r"\s+", " ", s).strip(" -._")
    return (s[:max_len] or "untitled").rstrip(" -._")


def _yaml_str(s: str) -> str:
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _unique_path(base: Path, date_str: str, slug: str) -> Path:
    candidate = base / f"{date_str}_{slug}.md"
    i = 2
    while candidate.exists():
        candidate = base / f"{date_str}_{slug}_{i}.md"
        i += 1
    return candidate


def _render_raw(candidate: Candidate, score: ScoreResult, *, now: datetime) -> str:
    date_str = now.strftime("%Y-%m-%d")
    ts_str = now.strftime("%Y-%m-%d %H:%M")
    fm = [
        "---",
        f"title: {_yaml_str(candidate.title)}",
        f"source: {candidate.source_url}",
        "source_type: article",
        'author: ""',
        f"created: {date_str}",
        f"published: {_yaml_str(candidate.published)}",
        "tags:",
        "  - raw/article",
        "  - clippings",
        f"  - discover/{candidate.source}",
        "ingested: false",
        f"discover_score: {score.score}",
        f"discover_reason: {_yaml_str(score.reason)}",
    ]
    if candidate.original_url:
        fm.append(f"discover_original_url: {candidate.original_url}")
    fm.append("---")
    parts: list[str] = ["\n".join(fm), "", f"# {candidate.title}", ""]
    if candidate.is_meta:
        parts += [
            candidate.summary.strip() or "_(메타 페이지 요약 없음)_",
            "",
            "## My Takes",
            "",
            "",
            "---",
            "",
            f"<!-- AUTO-APPENDED BY AI {ts_str} (KST) -->",
            "## 📎 원문 (auto-fetched from meta)",
            "",
            f"> 원본 URL: {candidate.original_url or '_(추출 실패)_'}",
            f"> 메타 페이지: {candidate.source_url}",
            f"> 페치 시점: {ts_str} (KST)",
            "",
            candidate.body.strip() or "_(원문 본문 추출 실패)_",
            "<!-- /AUTO-APPENDED -->",
        ]
    else:
        parts.append(candidate.body.strip() or candidate.summary.strip())
    parts += [
        "",
        "## Discover 메모",
        "",
        f"- 점수: {score.score}/5 (임계값 {SCORE_THRESHOLD})",
        f"- 이유: {score.reason}",
        f"- 트리거: process_daily.py ({date_str})",
        "",
    ]
    return "\n".join(parts)


def _candidate_urls_in_raw() -> set[str]:
    """Just raw/articles. Must NOT include daily-file URLs (those are the
    candidates we're about to process), which dedupe.existing_urls() would
    pick up."""
    return {dedupe.normalize_url(u) for u in dedupe.urls_in_raw() if u}


def process_daily(daily_path: Path, *, now: datetime | None = None) -> ProcessResult:
    now = now or datetime.now()
    entries: list[DailyEntry] = parse_daily(daily_path)
    date_str = daily_path.stem  # YYYY-MM-DD

    accepted = [e for e in entries if e.decision == Decision.ACCEPTED]
    dismissed = [e for e in entries if e.decision == Decision.DISMISSED]
    pending = [e for e in entries if e.decision == Decision.PENDING]

    raw_dir = raw_articles_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)

    existing = _candidate_urls_in_raw()
    written: list[Path] = []
    skipped_existing: list[str] = []

    for entry in accepted:
        cand = entry.candidate
        norm_urls = {
            dedupe.normalize_url(cand.source_url),
            dedupe.normalize_url(cand.original_url or ""),
        }
        if any(u in existing for u in norm_urls if u):
            skipped_existing.append(cand.source_url)
            continue
        target = _unique_path(raw_dir, date_str, _slugify(cand.title))
        target = ensure_writable(target)
        target.write_text(_render_raw(cand, entry.score, now=now), encoding="utf-8")
        written.append(target)
        for u in norm_urls:
            if u:
                existing.add(u)

    feedback_entries: list[dict] = []
    for entry in accepted + dismissed:
        feedback_entries.append(
            {
                "date": date_str,
                "slot": entry.slot,
                "source": entry.candidate.source,
                "title": entry.candidate.title,
                "url": entry.candidate.source_url,
                "original_url": entry.candidate.original_url,
                "decision": entry.decision.value,
                "score": entry.score.score,
                "reason": entry.score.reason,
            }
        )

    feedback_count = append_decisions(feedback_entries)
    feedback_profile.recompute()

    return ProcessResult(
        daily_path=daily_path,
        date=date_str,
        accepted=len(accepted),
        dismissed=len(dismissed),
        pending=len(pending),
        raw_written=written,
        raw_skipped_existing=skipped_existing,
        feedback_appended=feedback_count,
    )
