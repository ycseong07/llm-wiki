"""Vector search + Maximal Marginal Relevance (MMR) rerank.

Flow: query -> embed -> Qdrant top-K -> MMR -> top-N.
Embeddings are L2-normalized (see embedder.embed), so dot product == cosine sim.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.eval.behavior import REPEAT_THRESHOLD, record_query
from src.eval.metrics import retrieval_metrics
from src.eval.tracing import get_client as _lf_client
from src.eval.tracing import observe
from src.index.embedder import embed
from src.index.qdrant import COLLECTION, get_client


@dataclass
class Hit:
    score: float
    title: str
    source: str
    category: str
    url: str
    chunk_text: str
    vault_path: str


def _mmr(
    query_vec: np.ndarray,
    candidate_vecs: np.ndarray,
    lambda_: float,
    top_n: int,
) -> list[int]:
    """Return indices of selected candidates in selection order."""
    if len(candidate_vecs) == 0:
        return []
    sim_to_query = candidate_vecs @ query_vec
    selected: list[int] = []
    remaining = list(range(len(candidate_vecs)))
    while remaining and len(selected) < top_n:
        if not selected:
            best = max(remaining, key=lambda i: sim_to_query[i])
        else:
            sel_vecs = candidate_vecs[selected]
            best = max(
                remaining,
                key=lambda i: (
                    lambda_ * sim_to_query[i]
                    - (1.0 - lambda_) * float((candidate_vecs[i] @ sel_vecs.T).max())
                ),
            )
        selected.append(best)
        remaining.remove(best)
    return selected


@observe(name="search")
def search(
    query: str,
    top_n: int = 5,
    candidate_k: int = 20,
    mmr_lambda: float = 0.5,
    category: str | None = None,
) -> list[Hit]:
    qv = embed([query])[0]

    qfilter = None
    if category:
        from qdrant_client.http import models as qm

        qfilter = qm.Filter(
            must=[qm.FieldCondition(key="category", match=qm.MatchValue(value=category))]
        )

    resp = get_client().query_points(
        collection_name=COLLECTION,
        query=qv.tolist(),
        limit=candidate_k,
        with_vectors=True,
        with_payload=True,
        query_filter=qfilter,
    )
    hits = resp.points
    if not hits:
        return []

    cand_vecs = np.array([h.vector for h in hits], dtype=np.float32)

    # PROJECT_PLAN §8.2 Layer A + B — best-effort, never raise.
    try:
        lf = _lf_client()
        for name, value in retrieval_metrics(cand_vecs, [h.score for h in hits]).items():
            lf.score_current_span(name=name, value=value)
        repeat_sim = record_query(qv)
        lf.score_current_span(name="repeat_similarity", value=repeat_sim)
        if repeat_sim >= REPEAT_THRESHOLD:
            lf.update_current_trace(tags=["repeat_query"])
    except Exception:
        pass

    order = _mmr(qv, cand_vecs, lambda_=mmr_lambda, top_n=top_n)
    return [
        Hit(
            score=float(hits[i].score),
            title=hits[i].payload.get("title", ""),
            source=hits[i].payload.get("source", ""),
            category=hits[i].payload.get("category", ""),
            url=hits[i].payload.get("url", ""),
            chunk_text=hits[i].payload.get("chunk_text", ""),
            vault_path=hits[i].payload.get("vault_path", ""),
        )
        for i in order
    ]
