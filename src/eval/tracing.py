"""Langfuse tracing wiring.

Reads keys from Windows Credential Manager (keyring), exports them as env vars,
then re-exports `observe` / `get_client` / `flush`. If keys are missing the SDK
is replaced by no-op stubs so RAG keeps running without traces.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from src import credentials as c

_pub = c.get_secret(c.LANGFUSE_PUBLIC_KEY)
_sec = c.get_secret(c.LANGFUSE_SECRET_KEY)
ENABLED = bool(_pub and _sec)

if ENABLED:
    os.environ["LANGFUSE_PUBLIC_KEY"] = _pub  # type: ignore[arg-type]
    os.environ["LANGFUSE_SECRET_KEY"] = _sec  # type: ignore[arg-type]
    os.environ.setdefault("LANGFUSE_HOST", "http://127.0.0.1:3000")

    from langfuse import get_client, observe  # type: ignore  # noqa: E402,F401

    def flush() -> None:
        try:
            get_client().flush()
        except Exception as e:
            print(f"[tracing] flush failed: {e!r}")

else:
    def observe(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(fn: Callable) -> Callable:
            return fn

        return decorator

    class _NoopClient:
        def update_current_observation(self, **_: Any) -> None: ...
        def update_current_trace(self, **_: Any) -> None: ...
        def update_current_span(self, **_: Any) -> None: ...
        def update_current_generation(self, **_: Any) -> None: ...
        def flush(self) -> None: ...
        def shutdown(self) -> None: ...

    def get_client() -> Any:  # type: ignore[no-redef]
        return _NoopClient()

    def flush() -> None:
        pass
