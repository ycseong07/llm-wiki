"""Classify Gmail Newsletter entries into finance | ai | newsletter (generic).

RSS entries are passed through unchanged — feeds.yaml is the source of truth
for their category. Only Gmail entries (category="newsletter") get a Gemini call.
"""
from __future__ import annotations

from src.agents.nodes._gemini import generate
from src.agents.sources.rss import Entry

VALID = {"finance", "ai", "newsletter"}

PROMPT = """다음 글이 가장 가까운 카테고리 한 단어만 출력. 다른 텍스트 금지.
후보:
- finance: 증권/금융/경제/시장/기업/산업/거시지표
- ai: AI/머신러닝/LLM/모델/연구/도구/엔지니어링
- newsletter: 위 둘에 명확히 해당하지 않음

제목: {title}
본문 일부: {body}

답:"""


def classify_entry(entry: Entry) -> Entry:
    if entry.category != "newsletter":
        return entry
    if not entry.summary.strip():
        return entry
    prompt = PROMPT.format(title=entry.title, body=entry.summary[:2000])
    answer = generate(prompt).lower().split()
    if answer and answer[0] in VALID:
        entry.category = answer[0]
    return entry
