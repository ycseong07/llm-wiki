"""Project config — paths only.

Secret loading goes through `src/credentials.py` (keyring).
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def obsidian_vault_path() -> Path:
    raw = os.environ.get("OBSIDIAN_VAULT_PATH")
    if not raw:
        raise RuntimeError(
            "OBSIDIAN_VAULT_PATH is not set. Copy .env.example to .env and fill it in."
        )
    p = Path(raw).expanduser().resolve()
    if not p.is_dir():
        raise RuntimeError(f"OBSIDIAN_VAULT_PATH does not exist or is not a directory: {p}")
    return p


def wiki_dir() -> Path:
    return obsidian_vault_path() / "wiki"


def graphify_out_dir() -> Path:
    return obsidian_vault_path() / "graphify-out"


def user_context_path() -> Path:
    return obsidian_vault_path() / "나의 핵심 맥락.md"
