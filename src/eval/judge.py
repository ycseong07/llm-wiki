"""LLM-as-judge for RAG quality.

Three scores per (question, context, answer):
- faithfulness: answer grounded in context? (1.0 fully grounded, 0.0 hallucinated)
- answer_relevance: answer addresses the question directly?
- context_precision: retrieved context is relevant to the question?

Single judge (Gemini Flash). PROJECT_PLAN names Claude Haiku for cross-check
but ANTHROPIC_API_KEY is not provisioned here — we record agreement as None.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from src.agents.nodes._gemini import generate
from src.eval.tracing import observe

_PROMPT = """질문, 검색 context, 답변 3가지를 0.0~1.0 점수로 평가하라.
- faithfulness: 답변이 context 안 정보로 근거를 두는가? (1.0=완전 근거, 0.0=환각)
- answer_relevance: 답변이 질문에 직접 답하는가? (1.0=직접 답, 0.0=무관)
- context_precision: context가 질문 관련 정보를 담는가? (1.0=모두 관련, 0.0=무관)

JSON으로만 응답 (다른 텍스트 금지):
{{"faithfulness": 0.X, "answer_relevance": 0.X, "context_precision": 0.X}}

질문: {question}

Context:
{context}

답변: {answer}
"""


@dataclass
class JudgeResult:
    faithfulness: float
    answer_relevance: float
    context_precision: float


def _clamp(v) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


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


@observe(name="judge")
def judge(question: str, context: str, answer: str) -> JudgeResult:
    prompt = _PROMPT.format(question=question, context=context[:3000], answer=answer[:1500])
    raw = generate(prompt)
    parsed = _safe_json(raw)
    return JudgeResult(
        faithfulness=_clamp(parsed.get("faithfulness", 0.0)),
        answer_relevance=_clamp(parsed.get("answer_relevance", 0.0)),
        context_precision=_clamp(parsed.get("context_precision", 0.0)),
    )
