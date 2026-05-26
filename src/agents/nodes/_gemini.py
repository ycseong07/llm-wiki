"""Shared Gemini client + rate limiter.

Tier 1 `gemini-2.5-flash` (PROJECT_PLAN §3, 부록 B 2026-05-26): 2000 RPM / 10k RPD.
0.5s buffer is a sanity floor in case of accidental burst loops; real bottleneck
is Gemini latency (~2-3s/call), not this limit.
"""
from __future__ import annotations

import threading
import time

from google import genai

from src import credentials as c
from src.eval.tracing import get_client as _lf_client
from src.eval.tracing import observe

MODEL = "gemini-2.5-flash"
_MIN_INTERVAL_S = 0.5

_client: genai.Client | None = None
_lock = threading.Lock()
_last_call: float = 0.0


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=c.require_secret(c.GEMINI_API_KEY))
    return _client


@observe(as_type="generation", name="gemini")
def generate(prompt: str) -> str:
    global _last_call
    with _lock:
        elapsed = time.monotonic() - _last_call
        if elapsed < _MIN_INTERVAL_S:
            time.sleep(_MIN_INTERVAL_S - elapsed)
        resp = _get_client().models.generate_content(model=MODEL, contents=prompt)
        _last_call = time.monotonic()
    text = (resp.text or "").strip()
    try:
        usage = getattr(resp, "usage_metadata", None)
        usage_details: dict[str, int] = {}
        if usage:
            if getattr(usage, "prompt_token_count", None) is not None:
                usage_details["input"] = usage.prompt_token_count
            if getattr(usage, "candidates_token_count", None) is not None:
                usage_details["output"] = usage.candidates_token_count
        _lf_client().update_current_observation(model=MODEL, usage_details=usage_details or None)
    except Exception:
        pass
    return text
