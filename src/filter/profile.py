"""Load the user's intent profile from the Obsidian vault.

Signals used by the scorer to decide whether a candidate is worth recommending:
- entity + concept page names (what the user actively maintains pages about)
- wiki/index.md text (the curated catalog with one-line descriptions)
- 나의 핵심 맥락.md (the user's self-interview: roles, values, vision)
- graphify-out/GRAPH_REPORT.md (god nodes / communities, already digested)
- feedback/preference_profile.json (accepted / dismissed domains and sources)

Caching is process-level: each `discover_*` run loads once.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from src.config import graphify_out_dir, obsidian_vault_path, user_context_path, wiki_dir
from src.feedback import profile as feedback_profile


def _read(path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _top_items(counter: dict[str, int], n: int = 10) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[:n]


@dataclass
class Profile:
    page_names: set[str] = field(default_factory=set)
    wiki_index_text: str = ""
    user_context: str = ""
    graph_report_text: str = ""
    accepted_domains: dict[str, int] = field(default_factory=dict)
    dismissed_domains: dict[str, int] = field(default_factory=dict)

    def as_prompt_block(self) -> str:
        """Single text block injected into the scorer prompt."""
        parts: list[str] = []
        if self.user_context:
            parts.append("## 사용자 핵심 맥락\n" + self.user_context.strip())
        if self.wiki_index_text:
            parts.append("## 위키 인덱스 (관심 토픽 카탈로그)\n" + self.wiki_index_text.strip())
        if self.graph_report_text:
            parts.append(
                "## 지식 그래프 요약 (god nodes / communities)\n"
                + self.graph_report_text.strip()
            )
        if self.page_names:
            parts.append(
                "## 보유 위키 페이지명 (entity + concept)\n"
                + ", ".join(sorted(self.page_names))
            )
        fb = self._feedback_block()
        if fb:
            parts.append(fb)
        return "\n\n".join(parts)

    def _feedback_block(self) -> str:
        if not (self.accepted_domains or self.dismissed_domains):
            return ""
        lines = ["## 사용자 과거 선택 (참고 신호)"]
        if self.accepted_domains:
            lines.append(
                "- 자주 accepted된 도메인: "
                + ", ".join(f"{d}({c})" for d, c in _top_items(self.accepted_domains))
            )
        if self.dismissed_domains:
            lines.append(
                "- 자주 dismissed된 도메인: "
                + ", ".join(f"{d}({c})" for d, c in _top_items(self.dismissed_domains))
            )
        return "\n".join(lines)


def _collect_page_names() -> set[str]:
    names: set[str] = set()
    for sub in ("entities", "concepts"):
        d = wiki_dir() / sub
        if not d.is_dir():
            continue
        for p in d.glob("*.md"):
            names.add(p.stem)
    return names


@lru_cache(maxsize=1)
def load_profile() -> Profile:
    obsidian_vault_path()  # validates env
    fb = feedback_profile.load()
    return Profile(
        page_names=_collect_page_names(),
        wiki_index_text=_read(wiki_dir() / "index.md"),
        user_context=_read(user_context_path()),
        graph_report_text=_read(graphify_out_dir() / "GRAPH_REPORT.md"),
        accepted_domains=dict(fb.get("accepted_domains") or {}),
        dismissed_domains=dict(fb.get("dismissed_domains") or {}),
    )
