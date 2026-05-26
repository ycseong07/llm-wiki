"""REST endpoints (parallel to MCP for non-MCP clients / debugging)."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from src.eval.tracing import observe
from src.index.search import search
from src.server.audit import Timer, emit
from src.server.mcp_tools import list_recent

router = APIRouter(prefix="/v1")


class QueryRequest(BaseModel):
    query: str
    category: str | None = None
    limit: int = 5


@router.post("/query")
@observe(name="rest.query")
def query(req: QueryRequest) -> dict:
    with Timer() as t:
        hits = search(req.query, top_n=req.limit, category=req.category)
    emit("rest.query", query=req.query, category=req.category, hits=len(hits), ms=t.ms)
    return {"hits": [asdict(h) for h in hits]}


@router.get("/sources")
def sources(category: str | None = None, days: int = 1) -> dict:
    items = list_recent(category=category, days=days)
    return {"items": items, "count": len(items)}
