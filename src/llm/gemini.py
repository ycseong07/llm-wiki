"""Shared Gemini client + rate limiter.

Memory [[gemini-tier1]]: model `gemini-2.5-flash`, Tier 1 pay-as-you-go.
2.0-flash is blocked for new users; do not switch back without checking the memory.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from google import genai
from google.genai import types

from src import credentials as c

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


def _throttle() -> None:
    global _last_call
    elapsed = time.monotonic() - _last_call
    if elapsed < _MIN_INTERVAL_S:
        time.sleep(_MIN_INTERVAL_S - elapsed)
    _last_call = time.monotonic()


def generate(prompt: str, *, system: str | None = None) -> str:
    with _lock:
        _throttle()
        config = types.GenerateContentConfig(system_instruction=system) if system else None
        resp = _get_client().models.generate_content(
            model=MODEL, contents=prompt, config=config
        )
    return (resp.text or "").strip()


def generate_json(prompt: str, schema: dict[str, Any], *, system: str | None = None) -> dict:
    """Generate JSON matching schema. Raises on parse failure."""
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        system_instruction=system,
    )
    with _lock:
        _throttle()
        resp = _get_client().models.generate_content(
            model=MODEL, contents=prompt, config=config
        )
    return json.loads(resp.text or "{}")
