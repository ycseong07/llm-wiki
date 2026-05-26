"""MCP tools (registered with FastMCP) — RAG entry points for Mac Claude Code.

Tools per PROJECT_PLAN §6 Phase 4:
- search_documents: vector search + MMR
- list_recent: vault scan by published date / mtime
- get_daily_digest: read vault/00_Daily/daily.md (Phase 5 will populate this)
- get_by_tag: temporary alias to category until vault gains a tags field
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from src.config import VAULT_PATH
from src.eval.tracing import observe
from src.index.search import search
from src.server.audit import Timer, emit

# DNS rebinding protection: keep ON, whitelist tailnet host + localhost.
# If the tailnet machine name changes, update this list.
mcp = FastMCP(
    "obsidian-rag",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "llm-wiki.tailaa4612.ts.net",
            "127.0.0.1:*",
            "localhost:*",
        ],
    ),
)

VALID_CATEGORIES = {"finance", "ai", "newsletter", "community"}


@mcp.tool()
@observe(name="mcp.search_documents")
def search_documents(query: str, category: str | None = None, limit: int = 5) -> list[dict]:
    """Semantic search over the vault. Returns top-N chunks with payload."""
    with Timer() as t:
        hits = search(query, top_n=limit, category=category)
    emit("mcp.search_documents", query=query, category=category, limit=limit, hits=len(hits), ms=t.ms)
    return [asdict(h) for h in hits]


@mcp.tool()
@observe(name="mcp.list_recent")
def list_recent(category: str | None = None, days: int = 1) -> list[dict]:
    """List vault entries created within the last `days` days, newest first."""
    with Timer() as t:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        results: list[tuple[float, dict]] = []
        for path in VAULT_PATH.rglob("*.md"):
            if path.name.startswith("."):
                continue
            meta = _read_frontmatter(path)
            if category and meta.get("category") != category:
                continue
            mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                continue
            results.append((
                mtime.timestamp(),
                {
                    "title": _read_title(path),
                    "source": meta.get("source", ""),
                    "category": meta.get("category", ""),
                    "url": meta.get("url", ""),
                    "published": str(meta.get("published", "")),
                    "vault_path": path.as_posix(),
                },
            ))
        results.sort(key=lambda x: x[0], reverse=True)
    out = [r[1] for r in results]
    emit("mcp.list_recent", category=category, days=days, count=len(out), ms=t.ms)
    return out


@mcp.tool()
@observe(name="mcp.get_daily_digest")
def get_daily_digest(date: str | None = None) -> dict:
    """Return the Daily Digest markdown for `date` (YYYY-MM-DD) or today.

    Phase 5 writes vault/00_Daily/daily.md (today). Past digests are not retained
    by default. Returns {"date", "content", "found": bool}.
    """
    with Timer() as t:
        today = datetime.now(timezone.utc).date().isoformat()
        target_date = date or today
        digest_path = VAULT_PATH / "00_Daily" / "daily.md"
        if not digest_path.exists():
            result: dict[str, Any] = {"date": target_date, "content": "", "found": False}
        else:
            content = digest_path.read_text(encoding="utf-8")
            result = {"date": target_date, "content": content, "found": True}
    emit("mcp.get_daily_digest", date=target_date, found=result["found"], ms=t.ms)
    return result


@mcp.tool()
@observe(name="mcp.get_by_tag")
def get_by_tag(tag: str) -> list[dict]:
    """Return entries matching `tag`.

    Phase 4 limitation: vault has no `tags` frontmatter field yet, so tag is
    aliased to category. Valid tags: finance, ai, newsletter, community.
    """
    if tag not in VALID_CATEGORIES:
        emit("mcp.get_by_tag", tag=tag, error="unknown_tag")
        return []
    return list_recent(category=tag, days=30)


def _read_frontmatter(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        return {}
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        return yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}


def _read_title(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem
