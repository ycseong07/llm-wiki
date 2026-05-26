"""Daily digest builder — runs once per day at 07:00 via Task Scheduler.

Scans vault for files written in the previous 24h window (mtime-based),
groups by category, calls Gemini ONCE per category for a category-level summary
plus per-entry importance score (1-5), checks continuity vs yesterday's digest
via embedding similarity, and renders `vault/00_Daily/daily.md`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np
import yaml

from src.agents.nodes._gemini import generate
from src.config import VAULT_PATH

CATEGORIES_ORDER = ["finance", "ai", "newsletter", "community"]
CATEGORY_DIRS = {
    "finance": "10_Finance",
    "ai": "20_AI",
    "newsletter": "30_Newsletters",
    "community": "40_HadaIO",
}
CATEGORY_LABELS = {
    "finance": "증권/금융/경제",
    "ai": "AI/기술",
    "newsletter": "뉴스레터",
    "community": "news.hada.io",
}
DIGEST_DIR = VAULT_PATH / "00_Daily"
DIGEST_PATH = DIGEST_DIR / "daily.md"

CONTINUITY_THRESHOLD = 0.7  # cosine sim above this -> "지속 추적" flag


@dataclass
class Entry:
    title: str
    source: str
    url: str
    summary: str
    category: str
    vault_path: Path
    importance: int = 3
    continuity: bool = False


def _read_frontmatter(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}, raw
    try:
        return yaml.safe_load(parts[1]) or {}, parts[2].lstrip("\n")
    except yaml.YAMLError:
        return {}, parts[2].lstrip("\n")


def _title_from_body(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _summary_from_body(body: str) -> str:
    # Body starts with `# Title`, then blank, then summary paragraph(s), then `[원문](...)`.
    paragraphs: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("[원문]"):
            continue
        paragraphs.append(line)
        if len("\n".join(paragraphs)) > 800:
            break
    return "\n".join(paragraphs)


def _window() -> tuple[datetime, datetime]:
    """Yesterday 07:00 ~ today 07:00 in local tz."""
    now = datetime.now().astimezone()
    today_seven = datetime.combine(now.date(), time(7, 0)).astimezone(now.tzinfo)
    if now < today_seven:
        today_seven = today_seven - timedelta(days=1)
    return today_seven - timedelta(days=1), today_seven


def collect_entries(start: datetime, end: datetime) -> list[Entry]:
    entries: list[Entry] = []
    for cat, subdir in CATEGORY_DIRS.items():
        folder = VAULT_PATH / subdir
        if not folder.exists():
            continue
        for path in folder.glob("*.md"):
            if path.name.startswith("."):
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).astimezone()
            if not (start <= mtime < end):
                continue
            meta, body = _read_frontmatter(path)
            entries.append(
                Entry(
                    title=_title_from_body(body, path.stem),
                    source=meta.get("source", ""),
                    url=meta.get("url", ""),
                    summary=_summary_from_body(body),
                    category=cat,
                    vault_path=path,
                )
            )
    return entries


_CAT_PROMPT = """다음은 오늘 수집된 '{category_label}' 카테고리 콘텐츠 목록이다.
1) 카테고리 전체에서 가장 중요한 흐름 2~3문장 한국어 요약
2) 각 엔트리에 1~5 중요도 점수 (5=매일 봐야 함, 1=배경 정보)

JSON으로만 응답. 다른 텍스트 금지:
{{
  "category_summary": "...",
  "scores": [{{"i": 0, "score": 5}}, {{"i": 1, "score": 3}}, ...]
}}

콘텐츠:
{items}
"""


def enrich_with_llm(entries_by_cat: dict[str, list[Entry]]) -> dict[str, str]:
    """One Gemini call per category. Mutates Entry.importance in-place."""
    category_summaries: dict[str, str] = {}
    for cat, group in entries_by_cat.items():
        if not group:
            continue
        items_text = "\n\n".join(
            f"[{i}] 제목: {e.title}\n출처: {e.source}\n요약: {e.summary[:400]}"
            for i, e in enumerate(group)
        )
        prompt = _CAT_PROMPT.format(category_label=CATEGORY_LABELS[cat], items=items_text)
        raw = generate(prompt)
        parsed = _safe_json(raw)
        category_summaries[cat] = parsed.get("category_summary", "")
        for score_entry in parsed.get("scores", []) or []:
            i, score = score_entry.get("i"), score_entry.get("score")
            if isinstance(i, int) and isinstance(score, int) and 0 <= i < len(group):
                group[i].importance = max(1, min(5, score))
    return category_summaries


def _safe_json(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip("` \n")
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return {}


def mark_continuity(entries: list[Entry]) -> None:
    """Set entry.continuity=True if topic overlaps yesterday's digest (cosine >= threshold)."""
    if not entries or not DIGEST_PATH.exists():
        return
    yesterday = DIGEST_PATH.read_text(encoding="utf-8")
    if not yesterday.strip():
        return
    from src.index.embedder import embed  # local import: bge-m3 takes ~10s to load

    y_vec = embed([yesterday])[0]
    e_vecs = embed([f"{e.title}\n{e.summary[:300]}" for e in entries])
    sims = e_vecs @ y_vec  # vectors are L2-normalized
    for e, s in zip(entries, sims):
        if float(s) >= CONTINUITY_THRESHOLD:
            e.continuity = True


def render(category_summaries: dict[str, str], entries_by_cat: dict[str, list[Entry]]) -> str:
    now = datetime.now().astimezone()
    total = sum(len(g) for g in entries_by_cat.values())
    lines: list[str] = []
    lines.append(f"# {now.date().isoformat()} Daily Digest")
    lines.append("")
    lines.append(f"> 신규 {total}건 · 생성 {now.strftime('%H:%M')}")
    lines.append("")

    if total == 0:
        lines.append("어제 새로 수집된 콘텐츠 없음.")
        lines.append("")
        return "\n".join(lines)

    for cat in CATEGORIES_ORDER:
        group = entries_by_cat.get(cat) or []
        if not group:
            continue
        lines.append(f"## {CATEGORY_LABELS[cat]} ({len(group)}건)")
        lines.append("")
        cat_sum = category_summaries.get(cat, "").strip()
        if cat_sum:
            lines.append(f"> {cat_sum}")
            lines.append("")
        group_sorted = sorted(group, key=lambda e: e.importance, reverse=True)
        for e in group_sorted:
            stars = "⭐" * e.importance
            cont = " 🔁" if e.continuity else ""
            link = f"[원문]({e.url})" if e.url else ""
            src = f"`{e.source}`" if e.source else ""
            lines.append(f"- **{e.title}** {stars}{cont} — {e.summary.splitlines()[0] if e.summary else ''} {link} {src}".rstrip())
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 🔗 빠른 검색")
    lines.append("- Mac Claude Code: `obsidian-rag MCP로 ... 찾아줘`")
    lines.append("")
    return "\n".join(lines)


def build_digest() -> dict:
    start, end = _window()
    entries = collect_entries(start, end)

    entries_by_cat: dict[str, list[Entry]] = {cat: [] for cat in CATEGORIES_ORDER}
    for e in entries:
        entries_by_cat.setdefault(e.category, []).append(e)

    if entries:
        category_summaries = enrich_with_llm(entries_by_cat)
        mark_continuity(entries)
    else:
        category_summaries = {}

    content = render(category_summaries, entries_by_cat)
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    DIGEST_PATH.write_text(content, encoding="utf-8")

    return {
        "path": str(DIGEST_PATH),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "total": len(entries),
        "per_category": {cat: len(g) for cat, g in entries_by_cat.items() if g},
    }
