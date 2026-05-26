"""FastAPI entrypoint.

Phase 1: only `/v1/health` for Tailscale reachability check.
Phase 4 will add `/mcp`, `/v1/query`, `/v1/sources`, JWT middleware, rate limit, audit log.
"""
from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="llm_wiki", version="0.1.0")


@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
