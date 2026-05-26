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
from src.agents.nodes.fulltext import fetch_fulltext
from src.agents.nodes.link_expander import expand_links
from src.agents.nodes.summarizer import unified_summarize
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


def fulltext_node(state: State) -> dict:
    entries = state["entries"]
    before_len = sum(len(e.summary) for e in entries)
    enriched = [fetch_fulltext(e) for e in entries]
    after_len = sum(len(e.summary) for e in enriched)
    upgraded = sum(1 for b, a in zip(entries, enriched) if len(a.summary) > len(b.summary))
    print(f"[fulltext] upgraded={upgraded}/{len(entries)}  body bytes {before_len} -> {after_len}")
    return {"entries": enriched}


def expand_links_node(state: State) -> dict:
    entries = [expand_links(e) for e in state["entries"]]
    total_links = sum(len(e.linked_contents) for e in entries)
    with_links = sum(1 for e in entries if e.linked_contents)
    print(f"[expand_links] {with_links}/{len(entries)} entries got linked contents, total fetched={total_links}")
    return {"entries": entries}


def unified_summarize_node(state: State) -> dict:
    out = [unified_summarize(e) for e in state["entries"]]
    return {"entries": out}


def classify_node(state: State) -> dict:
    out = [classify_entry(e) for e in state["entries"]]
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
    g.add_node("fulltext", fulltext_node)
    g.add_node("expand_links", expand_links_node)
    g.add_node("unified_summarize", unified_summarize_node)
    g.add_node("classify", classify_node)
    g.add_node("write", write_node)
    g.set_entry_point("fetch")
    g.add_edge("fetch", "dedupe")
    g.add_edge("dedupe", "exists_filter")
    g.add_edge("exists_filter", "fulltext")
    g.add_edge("fulltext", "expand_links")
    g.add_edge("expand_links", "unified_summarize")
    g.add_edge("unified_summarize", "classify")
    g.add_edge("classify", "write")
    g.add_edge("write", END)
    return g.compile()
