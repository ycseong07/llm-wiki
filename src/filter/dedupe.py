"""Drop candidates whose URL already exists under raw/articles/.

Reads frontmatter from every raw/articles/*.md once per run, normalizes URLs
(strip tracking params, lowercase host, drop fragment + trailing slash), and
filters incoming candidates against that set.
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Iterable
from urllib.parse import parse_qsl, urlparse, urlunparse

import yaml

from src.config import raw_articles_dir
from src.sources.base import Candidate

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


@lru_cache(maxsize=1)
def existing_urls() -> frozenset[str]:
    out: set[str] = set()
    d = raw_articles_dir()
    if not d.is_dir():
        return frozenset()
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
    return frozenset(out)


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
