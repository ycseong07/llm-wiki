"""One discovery cycle: fetch -> dedupe -> score -> write raw candidates.

All vault writes go through `_write_raw_candidate` which validates the target
path is strictly inside `raw/articles/`. Anything else raises ValueError.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable, Iterator

from src.config import raw_articles_dir
from src.filter import dedupe, scorer
from src.filter.profile import load_profile
from src.sources.base import Candidate

KST = timezone(timedelta(hours=9))
_INVALID_FS = '<>:"/\\|?*'


@dataclass
class DiscoverResult:
    fetched: int
    after_dedupe: int
    scored: int
    passed: int
    written_paths: list[Path]
    skipped: list[tuple[str, int, str]]  # (title, score, reason)


def slugify(title: str, max_len: int = 60) -> str:
    s = title.strip()
    for ch in _INVALID_FS:
        s = s.replace(ch, "-")
    s = re.sub(r"\s+", " ", s).strip(" -._")
    return (s[:max_len] or "untitled").rstrip(" -._")


def _ensure_inside_raw_articles(path: Path) -> Path:
    base = raw_articles_dir().resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(base)
    except ValueError as e:
        raise ValueError(f"Refusing to write outside raw/articles/: {resolved}") from e
    return resolved


def _unique_path(base: Path, date_str: str, slug: str) -> Path:
    candidate = base / f"{date_str}_{slug}.md"
    i = 2
    while candidate.exists():
        candidate = base / f"{date_str}_{slug}_{i}.md"
        i += 1
    return candidate


def _render(candidate: Candidate, score: scorer.ScoreResult, now: datetime) -> str:
    date_str = now.strftime("%Y-%m-%d")
    ts_str = now.strftime("%Y-%m-%d %H:%M")
    fm_lines = [
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
        fm_lines.append(f"discover_original_url: {candidate.original_url}")
    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    body_parts: list[str] = [frontmatter, "", f"# {candidate.title}", ""]

    if candidate.is_meta:
        body_parts += [
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
        body_parts.append(candidate.body.strip() or candidate.summary.strip())

    body_parts += [
        "",
        "## Discover 메모",
        "",
        f"- 점수: {score.score}/5 (임계값 {scorer.SCORE_THRESHOLD})",
        f"- 이유: {score.reason}",
        f"- 트리거: scripts/discover_{candidate.source}.py ({date_str})",
        "",
    ]
    return "\n".join(body_parts)


def _yaml_str(s: str) -> str:
    """Minimal YAML-safe quoting. We always quote to dodge edge cases."""
    s = (s or "").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _write_raw_candidate(candidate: Candidate, score: scorer.ScoreResult, *, now: datetime) -> Path:
    base = raw_articles_dir()
    base.mkdir(parents=True, exist_ok=True)
    date_str = now.strftime("%Y-%m-%d")
    target = _unique_path(base, date_str, slugify(candidate.title))
    target = _ensure_inside_raw_articles(target)
    target.write_text(_render(candidate, score, now), encoding="utf-8")
    return target


def discover(
    source_fetch: Callable[[], Iterator[Candidate]],
    *,
    limit: int | None = None,
    dry_run: bool = False,
    now: datetime | None = None,
) -> DiscoverResult:
    now = now or datetime.now(KST)
    fetched = list(source_fetch())
    if limit is not None:
        fetched = fetched[:limit]
    fresh = dedupe.filter_new(fetched)

    profile = load_profile()
    written: list[Path] = []
    skipped: list[tuple[str, int, str]] = []
    scored_count = 0
    passed_count = 0

    for cand in fresh:
        result = scorer.score(cand, profile)
        scored_count += 1
        if not scorer.passes(result):
            skipped.append((cand.title, result.score, result.reason))
            continue
        passed_count += 1
        if dry_run:
            continue
        path = _write_raw_candidate(cand, result, now=now)
        written.append(path)

    return DiscoverResult(
        fetched=len(fetched),
        after_dedupe=len(fresh),
        scored=scored_count,
        passed=passed_count,
        written_paths=written,
        skipped=skipped,
    )
