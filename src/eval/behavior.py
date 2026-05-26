"""Behavior signal: repeat-query rate via 30-min rolling window of query embeddings.

PROJECT_PLAN §8.2 Layer B. Cosine sim >= 0.8 against any recent query => repeat.
"""
from __future__ import annotations

import time
from collections import deque
from threading import Lock

import numpy as np

WINDOW_S = 30 * 60
REPEAT_THRESHOLD = 0.8

_history: deque[tuple[float, np.ndarray]] = deque()
_lock = Lock()


def record_query(query_vec: np.ndarray) -> float:
    """Return max cosine sim against queries in the last WINDOW_S (0 if none).
    Records the new query into the window after computing the score.
    Vectors must be L2-normalized.
    """
    now = time.monotonic()
    qv = np.ascontiguousarray(query_vec, dtype=np.float32)
    with _lock:
        while _history and now - _history[0][0] > WINDOW_S:
            _history.popleft()
        max_sim = 0.0
        for _, vec in _history:
            sim = float(qv @ vec)
            if sim > max_sim:
                max_sim = sim
        _history.append((now, qv.copy()))
    return round(max_sim, 4)
