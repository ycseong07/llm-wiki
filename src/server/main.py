"""FastAPI entrypoint — REST + MCP + watcher + bge-m3 preload.

PROJECT_PLAN Phase 4: serves Mac Claude Code via MCP `/mcp` and REST `/v1/*`.
Watcher runs in-process so the same server handles vault changes incrementally.
JWT middleware is intentionally absent — see PROJECT_PLAN §4 Layer 2 (Tailscale
single-user, JWT optional).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from watchdog.observers import Observer

from src.config import VAULT_PATH
from src.index.embedder import _get_model
from src.index.qdrant import ensure_collection
from src.index.watcher import VaultHandler
from src.server.audit import emit
from src.server.mcp_tools import mcp
from src.server.rest import router as rest_router

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    emit("server.startup", vault_path=str(VAULT_PATH))
    ensure_collection()
    _get_model()  # preload bge-m3 so first /v1/query is fast

    observer = Observer()
    if VAULT_PATH.exists():
        observer.schedule(VaultHandler(), str(VAULT_PATH), recursive=True)
        observer.start()
        emit("server.watcher_started", vault_path=str(VAULT_PATH))
    else:
        emit("server.watcher_skipped", reason="vault_not_found", vault_path=str(VAULT_PATH))

    async with mcp.session_manager.run():
        try:
            yield
        finally:
            observer.stop()
            observer.join(timeout=5)
            emit("server.shutdown")


app = FastAPI(title="llm_wiki", version="0.2.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(rest_router)


@app.get("/v1/health")
@limiter.exempt
def health(request: Request) -> dict[str, str]:
    return {"status": "ok"}


# MCP mount LAST so FastAPI routes (/v1/*, /docs, etc.) take precedence in match order.
# The sub-app exposes /mcp internally, so mounting at "/" exposes external /mcp.
app.mount("/", mcp.streamable_http_app())
