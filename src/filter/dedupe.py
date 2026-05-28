"""Drop candidates whose URL has already been seen.

Three sources of "seen":
1. raw/articles/*.md frontmatter (already-ingested clippings)
2. daily/*.md candidate data blocks (already proposed today or past days)
3. feedback/candidate_decisions.jsonl (accepted or dismissed)

URL normalization strips tracking params, lowercases host, drops fragment and
trailing slash, so http vs https + utm noise won't slip through.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Iterable
from urllib.parse import parse_qsl, urlparse, urlunparse

import yaml

from src.daily.render import DATA_CLOSE, DATA_OPEN
from src.feedback.store import all_decision_urls
from src.sources.base import Candidate
from src.vault.paths import daily_dir, raw_articles_dir

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src",
}


def normalize_url(url: str) -> str:
    if not url:
        return ""
    try:
        u = urlparse(url.strip().rstrip(".,);"))
    except Exception:
        return ""
    if u.scheme not in ("http", "https") or not u.netloc:
        return ""
    cleaned_q = [
        (k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
        if k.lower() not in _TRACKING_PARAMS
    ]
    new_query = "&".join(f"{k}={v}" if v else k for k, v in cleaned_q)
    return urlunparse((
        u.scheme.lower(),
        u.netloc.lower(),
        u.path.rstrip("/"),
        "",
        new_query,
        "",
    ))


def _parse_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def urls_in_raw() -> set[str]:
    """Public: just the URLs already written under raw/articles/.

    process_daily needs this (not the full existing_urls()) so it doesn't see
    candidates' own URLs in the daily file we just generated.
    """
    return _urls_from_raw()


def _urls_from_raw() -> set[str]:
    out: set[str] = set()
    d = raw_articles_dir()
    if not d.is_dir():
        return out
    for p in d.glob("*.md"):
        try:
            fm = _parse_frontmatter(p.read_text(encoding="utf-8"))
        except OSError:
            continue
        for key in ("source", "source_url", "url", "original_url"):
            val = fm.get(key)
            if isinstance(val, str):
                norm = normalize_url(val)
                if norm:
                    out.add(norm)
    return out


def _urls_from_daily() -> set[str]:
    out: set[str] = set()
    d = daily_dir()
    if not d.is_dir():
        return out
    for p in d.glob("*.md"):
        try:
            text = p.read_text(encoding="utf-8")
        except OSError:
            continue
        start = text.rfind(DATA_OPEN)
        if start == -1:
            continue
        end = text.find(DATA_CLOSE, start)
        if end == -1:
            continue
        for line in text[start + len(DATA_OPEN) : end].splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            for key in ("source_url", "original_url"):
                v = item.get(key)
                if isinstance(v, str):
                    norm = normalize_url(v)
                    if norm:
                        out.add(norm)
    return out


def _urls_from_decisions() -> set[str]:
    out: set[str] = set()
    for url in all_decision_urls():
        norm = normalize_url(url)
        if norm:
            out.add(norm)
    return out


@lru_cache(maxsize=1)
def existing_urls() -> frozenset[str]:
    return frozenset(_urls_from_raw() | _urls_from_daily() | _urls_from_decisions())


def filter_new(candidates: Iterable[Candidate]) -> list[Candidate]:
    seen = existing_urls()
    fresh_norms: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:
        urls = [normalize_url(c.source_url), normalize_url(c.original_url or "")]
        if any(u in seen for u in urls if u):
            continue
        if any(u in fresh_norms for u in urls if u):
            continue
        for u in urls:
            if u:
                fresh_norms.add(u)
        out.append(c)
    return out
