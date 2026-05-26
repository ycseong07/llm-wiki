"""Retrieval-side metrics — PROJECT_PLAN §8.2 Layer A (non-LLM, every query).

Cheap to compute; emitted as Langfuse scores on the current span so they show
up next to the search trace.
"""
from __future__ import annotations

import numpy as np


def retrieval_metrics(
    candidate_vecs: np.ndarray,
    candidate_scores: list[float],
) -> dict[str, float]:
    """Return per-search retrieval metrics. Vectors are assumed L2-normalized."""
    n = len(candidate_scores)
    if n == 0:
        return {"top1_score": 0.0, "score_spread": 0.0, "diversity": 0.0}

    top1 = float(candidate_scores[0])
    last_idx = min(n - 1, 4)
    spread = top1 - float(candidate_scores[last_idx])

    if n < 2:
        diversity = 0.0
    else:
        sim = candidate_vecs @ candidate_vecs.T
        iu = np.triu_indices(n, k=1)
        diversity = float(1.0 - sim[iu].mean())

    return {
        "top1_score": round(top1, 4),
        "score_spread": round(spread, 4),
        "diversity": round(diversity, 4),
    }
