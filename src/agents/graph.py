"""LangGraph ingest pipeline: fetch -> dedupe -> exists_filter -> classify -> summarize -> write.

State is a list of Entry. Exists filter runs BEFORE LLM nodes so already-imported
entries don't burn Gemini quota.
"""
from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.agents.nodes.classifier import classify_entry
from src.agents.nodes.deduplicator import dedupe_by_url
from src.agents.nodes.summarizer import summarize_entry
from src.agents.nodes.vault_writer import target_path, write_entry
from src.agents.sources.gmail import fetch_recent as fetch_gmail
from src.agents.sources.rss import Entry, fetch_all as fetch_rss
from src.config import VAULT_PATH

FEEDS_YAML = Path(__file__).resolve().parent / "sources" / "feeds.yaml"


class State(TypedDict, total=False):
    entries: list[Entry]
    written: int


def fetch_node(_: State) -> dict:
    rss = list(fetch_rss(FEEDS_YAML))
    try:
        gmail = list(fetch_gmail())
    except Exception as e:
        print(f"[fetch] Gmail skipped: {e!r}")
        gmail = []
    print(f"[fetch] RSS={len(rss)} Gmail={len(gmail)}")
    return {"entries": rss + gmail}


def dedupe_node(state: State) -> dict:
    out = list(dedupe_by_url(state["entries"]))
    print(f"[dedupe] {len(state['entries'])} -> {len(out)}")
    return {"entries": out}


def exists_node(state: State) -> dict:
    out = [e for e in state["entries"] if not target_path(e, VAULT_PATH).exists()]
    print(f"[exists] {len(state['entries'])} -> {len(out)} new")
    return {"entries": out}


def classify_node(state: State) -> dict:
    out = [classify_entry(e) for e in state["entries"]]
    return {"entries": out}


def summarize_node(state: State) -> dict:
    out = [summarize_entry(e) for e in state["entries"]]
    return {"entries": out}


def write_node(state: State) -> dict:
    written = sum(1 for e in state["entries"] if write_entry(e, VAULT_PATH) is not None)
    print(f"[write] {written} files")
    return {"written": written}


def build_graph():
    g = StateGraph(State)
    g.add_node("fetch", fetch_node)
    g.add_node("dedupe", dedupe_node)
    g.add_node("exists_filter", exists_node)
    g.add_node("classify", classify_node)
    g.add_node("summarize", summarize_node)
    g.add_node("write", write_node)
    g.set_entry_point("fetch")
    g.add_edge("fetch", "dedupe")
    g.add_edge("dedupe", "exists_filter")
    g.add_edge("exists_filter", "classify")
    g.add_edge("classify", "summarize")
    g.add_edge("summarize", "write")
    g.add_edge("write", END)
    return g.compile()
