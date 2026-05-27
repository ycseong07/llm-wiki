"""Daily digest builder — runs once per day at 07:00 via Task Scheduler.

Scans vault for files written in the previous 24h window (mtime-based),
groups them into 3 buckets (AI/AX, 경제/주식, 기타), then asks Gemini to
**pick the top 3 per bucket with a one-line reason for each**. Renders
`vault/00_Daily/daily.md` as a 9-item digest readable in ~10 minutes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import yaml

from src.agents.nodes._gemini import generate
from src.config import VAULT_PATH

CATEGORIES_ORDER = ["ai", "finance", "etc"]
CATEGORY_LABELS = {
    "ai": "AI/AX",
    "finance": "경제/주식",
    "etc": "기타",
}
# Each digest bucket pulls from one or more vault subfolders. "etc" merges
# the newsletter + community folders into a single "everything else" pool.
CATEGORY_SOURCES = {
    "ai": ["20_AI"],
    "finance": ["10_Finance"],
    "etc": ["30_Newsletters", "40_HadaIO"],
}
DIGEST_DIR = VAULT_PATH / "00_Daily"
DIGEST_PATH = DIGEST_DIR / "daily.md"

PICKS_PER_CATEGORY = 3


@dataclass
class Entry:
    title: str
    source: str
    url: str
    summary: str
    category: str
    vault_path: Path
    picked: bool = False
    reason: str = ""


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
    """Full body of the article note (minus title/source link) so the LLM has
    enough context to judge importance and the renderer can extract a lead."""
    lines: list[str] = []
    for line in body.splitlines():
        if line.startswith("# ") or line.startswith("[원문]"):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _lead_paragraph(summary: str, max_chars: int = 280) -> str:
    for line in summary.splitlines():
        s = line.strip()
        if not s or s.startswith(("-", "*", "#", ">")):
            continue
        return s[:max_chars] + ("..." if len(s) > max_chars else "")
    return ""


def _window() -> tuple[datetime, datetime]:
    """Yesterday 07:00 ~ today 07:00 in local tz."""
    now = datetime.now().astimezone()
    today_seven = datetime.combine(now.date(), time(7, 0)).astimezone(now.tzinfo)
    if now < today_seven:
        today_seven = today_seven - timedelta(days=1)
    return today_seven - timedelta(days=1), today_seven


def collect_entries(start: datetime, end: datetime) -> list[Entry]:
    entries: list[Entry] = []
    for cat, subdirs in CATEGORY_SOURCES.items():
        for subdir in subdirs:
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
사용자는 매일 아침 약 10분 안에 이 카테고리를 훑고 싶다. 가장 중요한 {picks}개만 골라라.

선정 기준 (위쪽 가중치 높음):
1) 시장/판단/실무에 즉시 영향을 줄 만한가
2) 새로운 사실/발표/숫자 (회고·해설·재게시는 후순위)
3) 영향 범위 (해당 분야에서 많은 사람·기업에 적용되는가)
4) 같은 사건의 여러 보도 중 가장 1차에 가까운 자료

각 선정 항목에 대해 **왜 골랐는지를 한 문장 한국어**로 적어라.
이유는 "중요하다" 같은 동어반복이 아니라, 구체적 사실/숫자/맥락을 짧게 짚어야 한다.

JSON으로만 응답 (다른 텍스트 금지):
{{"picks": [{{"i": 0, "reason": "..."}}, {{"i": 3, "reason": "..."}}, {{"i": 7, "reason": "..."}}]}}

콘텐츠:
{items}
"""


def _format_items(entries: list[Entry]) -> str:
    return "\n\n".join(
        f"[{i}] 제목: {e.title}\n출처: {e.source}\n요약: {e.summary[:600]}"
        for i, e in enumerate(entries)
    )


def enrich_with_llm(entries_by_cat: dict[str, list[Entry]]) -> None:
    """One Gemini call per non-empty category. Marks `picked=True` and sets
    `reason` on up to PICKS_PER_CATEGORY entries in each group."""
    for cat, group in entries_by_cat.items():
        if not group:
            continue
        target = min(PICKS_PER_CATEGORY, len(group))
        prompt = _CAT_PROMPT.format(
            category_label=CATEGORY_LABELS[cat],
            picks=target,
            items=_format_items(group),
        )
        parsed = _safe_json(generate(prompt))
        picks = parsed.get("picks") or []
        marked = 0
        for p in picks:
            if marked >= PICKS_PER_CATEGORY:
                break
            i = p.get("i")
            reason = (p.get("reason") or "").strip()
            if isinstance(i, int) and 0 <= i < len(group) and not group[i].picked:
                group[i].picked = True
                group[i].reason = reason
                marked += 1
        # Fallback: LLM returned nothing usable -> just take first N so the
        # digest is never empty.
        if marked == 0:
            for e in group[:target]:
                e.picked = True


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


def render(entries_by_cat: dict[str, list[Entry]]) -> str:
    now = datetime.now().astimezone()
    total = sum(len(g) for g in entries_by_cat.values())
    picked_total = sum(sum(1 for e in g if e.picked) for g in entries_by_cat.values())

    lines: list[str] = []
    lines.append(f"# {now.date().isoformat()} Daily Digest")
    lines.append("")
    lines.append(f"> 신규 {total}건 중 {picked_total}건 선별 · 생성 {now.strftime('%H:%M')}")
    lines.append("")

    if total == 0:
        lines.append("어제 새로 수집된 콘텐츠 없음.")
        lines.append("")
        return "\n".join(lines)

    for cat in CATEGORIES_ORDER:
        group = entries_by_cat.get(cat) or []
        picked = [e for e in group if e.picked]
        if not picked:
            continue
        lines.append(f"## {CATEGORY_LABELS[cat]}  *(총 {len(group)}건 중 {len(picked)}건)*")
        lines.append("")
        for idx, e in enumerate(picked, 1):
            lines.append(f"### {idx}. {e.title}")
            if e.reason:
                lines.append(f"**왜 중요**: {e.reason}")
                lines.append("")
            lead = _lead_paragraph(e.summary)
            if lead:
                lines.append(lead)
                lines.append("")
            link_bits: list[str] = []
            if e.url:
                link_bits.append(f"[원문]({e.url})")
            link_bits.append(f"[[{e.vault_path.stem}|정리본]]")
            if e.source:
                link_bits.append(f"`{e.source}`")
            lines.append(" · ".join(link_bits))
            lines.append("")

    return "\n".join(lines)


def build_digest(window_days: int | None = None) -> dict:
    if window_days is None:
        start, end = _window()
    else:
        end = datetime.now().astimezone() + timedelta(hours=1)
        start = end - timedelta(days=window_days)
    entries = collect_entries(start, end)

    entries_by_cat: dict[str, list[Entry]] = {cat: [] for cat in CATEGORIES_ORDER}
    for e in entries:
        entries_by_cat.setdefault(e.category, []).append(e)

    if entries:
        enrich_with_llm(entries_by_cat)

    content = render(entries_by_cat)
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    DIGEST_PATH.write_text(content, encoding="utf-8")

    return {
        "path": str(DIGEST_PATH),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "total": len(entries),
        "picked": sum(sum(1 for e in g if e.picked) for g in entries_by_cat.values()),
        "per_category": {cat: len(g) for cat, g in entries_by_cat.items() if g},
    }
