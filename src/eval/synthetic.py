"""Weekly synthetic Q&A regression.

Sample random vault chunks → generate question from each → run RAG (search +
answer) → judge. Mean scores logged + threshold alerts to stdout.
PROJECT_PLAN §8.4 thresholds: faithfulness mean < 0.7 -> alert.
"""
from __future__ import annotations

import random
import statistics
from pathlib import Path

from src.agents.nodes._gemini import generate
from src.config import VAULT_PATH
from src.eval.judge import judge
from src.eval.tracing import observe
from src.index.indexer import walk_vault
from src.index.search import search

_QGEN = """다음 글을 읽고 사용자가 자연어로 물어볼 만한 질문 한 개를 한국어로 작성하라. 질문만 출력, 다른 텍스트 금지.

글:
{chunk}
"""

_ANSWER = """다음 context를 근거로 질문에 한국어 2~4문장으로 답하라. context에 없는 내용은 추측하지 말 것.

질문: {question}

Context:
{context}
"""

FAITHFULNESS_THRESHOLD = 0.7


def _strip_frontmatter(raw: str) -> str:
    if not raw.startswith("---"):
        return raw
    parts = raw.split("---", 2)
    return parts[2].strip() if len(parts) >= 3 else raw


def _sample(n: int) -> list[tuple[Path, str]]:
    files = list(walk_vault(VAULT_PATH))
    random.shuffle(files)
    out: list[tuple[Path, str]] = []
    for p in files:
        body = _strip_frontmatter(p.read_text(encoding="utf-8"))
        if len(body) >= 200:
            out.append((p, body))
        if len(out) >= n:
            break
    return out


@observe(name="weekly_eval")
def run_eval(n: int = 50) -> dict:
    samples = _sample(n)
    scores: dict[str, list[float]] = {
        "faithfulness": [],
        "answer_relevance": [],
        "context_precision": [],
    }

    for i, (path, body) in enumerate(samples, 1):
        try:
            question = generate(_QGEN.format(chunk=body[:1500])).strip()
            if not question:
                continue
            hits = search(question, top_n=3)
            if not hits:
                continue
            context = "\n\n".join(h.chunk_text for h in hits)
            answer = generate(_ANSWER.format(question=question, context=context[:3000]))
            r = judge(question, context, answer)
            scores["faithfulness"].append(r.faithfulness)
            scores["answer_relevance"].append(r.answer_relevance)
            scores["context_precision"].append(r.context_precision)
            print(f"[{i}/{len(samples)}] f={r.faithfulness:.2f} r={r.answer_relevance:.2f} p={r.context_precision:.2f}  {question[:60]}")
        except Exception as e:
            print(f"[{i}/{len(samples)}] error: {e!r}")

    summary: dict[str, dict[str, float]] = {}
    for k, vs in scores.items():
        if vs:
            summary[k] = {
                "mean": round(statistics.mean(vs), 4),
                "min": round(min(vs), 4),
                "max": round(max(vs), 4),
                "n": len(vs),
            }

    alerts: list[str] = []
    f_mean = summary.get("faithfulness", {}).get("mean")
    if f_mean is not None and f_mean < FAITHFULNESS_THRESHOLD:
        alerts.append(f"faithfulness mean {f_mean:.2f} < {FAITHFULNESS_THRESHOLD}")

    if alerts:
        print("\n=== ALERTS ===")
        for a in alerts:
            print(f"  - {a}")

    return {"summary": summary, "alerts": alerts, "sample_size": len(samples)}
