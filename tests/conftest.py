"""Shared fixtures: a fake OBSIDIAN_VAULT_PATH with the expected layout."""
from __future__ import annotations

import pytest


@pytest.fixture
def vault(tmp_path, monkeypatch):
    (tmp_path / "raw" / "articles").mkdir(parents=True)
    (tmp_path / "daily").mkdir()
    (tmp_path / "feedback" / "mac_references_inbox").mkdir(parents=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "index.md").write_text("# Wiki Index\n- foo\n", encoding="utf-8")
    (tmp_path / "나의 핵심 맥락.md").write_text("AI 엔지니어. 깊이 우선.\n", encoding="utf-8")
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "GRAPH_REPORT.md").write_text(
        "## God Nodes\n1. LLM Evaluation\n", encoding="utf-8"
    )
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))

    # Purge cached lookups so each test gets a clean read.
    from src.filter import dedupe
    from src.filter.profile import load_profile
    load_profile.cache_clear()
    dedupe.existing_urls.cache_clear()
    return tmp_path
