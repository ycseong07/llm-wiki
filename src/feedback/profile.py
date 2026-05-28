"""Aggregate decisions.jsonl → preference_profile.json.

Pure recompute from decisions — decisions is the source of truth, profile is a
derived cache that the scorer reads. Re-running is always safe.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from src.feedback.store import iter_decisions
from src.vault.paths import ensure_writable, feedback_dir

PROFILE_FILENAME = "preference_profile.json"


def profile_path() -> Path:
    return feedback_dir() / PROFILE_FILENAME


def _host(url: str) -> str:
    if not url:
        return ""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _empty_profile() -> dict:
    return {
        "accepted_topics": {},
        "dismissed_topics": {},
        "accepted_domains": {},
        "dismissed_domains": {},
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def recompute() -> dict:
    accepted_domains: Counter[str] = Counter()
    dismissed_domains: Counter[str] = Counter()
    accepted_sources: Counter[str] = Counter()
    dismissed_sources: Counter[str] = Counter()

    for entry in iter_decisions():
        decision = entry.get("decision")
        host = _host(entry.get("original_url") or entry.get("url") or "")
        src = str(entry.get("source") or "").strip()
        if decision == "accepted":
            if host:
                accepted_domains[host] += 1
            if src:
                accepted_sources[src] += 1
        elif decision == "dismissed":
            if host:
                dismissed_domains[host] += 1
            if src:
                dismissed_sources[src] += 1

    profile = _empty_profile()
    profile["accepted_domains"] = dict(accepted_domains)
    profile["dismissed_domains"] = dict(dismissed_domains)
    profile["accepted_topics"] = dict(accepted_sources)
    profile["dismissed_topics"] = dict(dismissed_sources)

    target = profile_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target = ensure_writable(target)
    target.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    return profile


def load() -> dict:
    path = profile_path()
    if not path.is_file():
        return _empty_profile()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_profile()
