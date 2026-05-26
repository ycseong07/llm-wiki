"""Unified summarization: synthesize the entry's body + every fetched
LinkedContent into ONE Korean summary + keyword tags.

This replaces the simple "summarize the snippet" pattern that lost information
by summarizing already-summarized text. Single Gemini call (cost-equivalent
to the previous summarizer, just with more input tokens).
"""
from __future__ import annotations

import json

from src.agents.nodes._gemini import generate
from src.agents.sources.rss import Entry

MAX_ORIGINAL_CHARS = 5000

PROMPT = """다음 자료를 통합해서 처리하라.
- 원본 글: 사용자가 직접 받은 콘텐츠 (요약본일 수도, 풀텍스트일 수도)
- 참조 글들: 원본 안에 인용된 외부 URL에서 가져온 실제 원본 콘텐츠

목표:
1) 원본 + 참조의 정보를 모두 활용한 한국어 5~8문장 통합 요약. 단순 합산이 아니라 핵심을 통합해 의미 손실을 최소화. 참조에만 있는 디테일(숫자/인명/회사명/기술명)을 적극 포함
2) 콘텐츠 전체를 대표하는 키워드/엔티티 3~5개 (고유명사·기술용어·회사명·인명 우선). 한·영 혼용 가능

JSON으로만 응답 (다른 텍스트 금지):
{{"summary": "...5~8문장...", "tags": ["키워드1", "키워드2", "키워드3"]}}

제목: {title}
출처: {source}

원본 글:
{body}
{linked_section}"""


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


def _linked_section(entry: Entry) -> str:
    if not entry.linked_contents:
        return ""
    parts = ["\n참조 글들 (원본 안 인용 URL에서 추출):"]
    for i, lc in enumerate(entry.linked_contents, 1):
        parts.append(f"\n[참조 {i}] {lc.url}\n{lc.text}")
    return "\n".join(parts)


def unified_summarize(entry: Entry) -> Entry:
    if not entry.summary.strip() and not entry.linked_contents:
        return entry
    prompt = PROMPT.format(
        title=entry.title,
        source=entry.source,
        body=entry.summary[:MAX_ORIGINAL_CHARS],
        linked_section=_linked_section(entry),
    )
    raw = generate(prompt)
    parsed = _safe_json(raw)
    summary = (parsed.get("summary") or "").strip()
    if summary:
        entry.summary = summary
    tags = parsed.get("tags") or []
    if isinstance(tags, list):
        entry.tags = [str(t).strip() for t in tags if str(t).strip()][:8]
    return entry


# Backward compatibility alias — graph.py still imports summarize_entry
summarize_entry = unified_summarize
