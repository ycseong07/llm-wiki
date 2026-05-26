"""Summarize entry content to 3~5 Korean sentences via Gemini Flash.

Replaces entry.summary in place. Handles raw HTML/markup by instructing the model
to ignore markup — no separate HTML parser needed.
"""
from __future__ import annotations

from src.agents.nodes._gemini import generate
from src.agents.sources.rss import Entry

PROMPT = """다음 콘텐츠를 한국어 3~5문장으로 핵심만 요약하라.
- HTML 태그/마크업은 무시
- 본문만 출력 (머리말/꼬리말/접두어 없음)
- 정보가 부족하면 짧게라도 가능한 범위까지

제목: {title}
출처: {source}

본문:
{body}
"""


def summarize_entry(entry: Entry) -> Entry:
    if not entry.summary.strip():
        return entry
    prompt = PROMPT.format(
        title=entry.title,
        source=entry.source,
        body=entry.summary[:5000],
    )
    summary = generate(prompt)
    if summary:
        entry.summary = summary
    return entry
