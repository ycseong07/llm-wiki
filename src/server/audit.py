"""JSON-line audit logger.

Writes one JSON object per line to logs/audit.log. Used by REST handlers and
MCP tools to record tool/endpoint calls with their args, latency, and outcome.
Never log secrets, full email bodies, or PII (CLAUDE.md §2.4).
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_FILE = LOG_DIR / "audit.log"

_lock = threading.Lock()
_initialized = False


def _init() -> None:
    global _initialized
    if _initialized:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _initialized = True


def emit(event: str, **fields: Any) -> None:
    _init()
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }
    line = json.dumps(record, ensure_ascii=False)
    with _lock:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


class Timer:
    """Context manager: `with Timer() as t: ...; t.ms` gives elapsed ms."""

    def __enter__(self) -> "Timer":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        self.ms = round((time.monotonic() - self._t0) * 1000, 1)
