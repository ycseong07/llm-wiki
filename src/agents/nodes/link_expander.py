"""Pull external URLs out of an entry's body, fetch each, attach as LinkedContent.

Newsletter bodies in particular curate external articles via URLs. Without
following them we summarize summaries — explicit information loss.

Caps to keep cost bounded:
- MAX_LINKS per entry (domain-diverse: first URL per distinct domain)
- MAX_CHARS_PER_LINK after extraction
- Skip self URL, gmail.com, mailto:, anchor-only, unsubscribe-ish links
- Strip tracking query params before dedup
"""
from __future__ import annotations

import re
from urllib.parse import parse_qsl, urlparse, urlunparse

from src.agents.nodes.fulltext import _fetch_html  # reuse UA + timeout
from src.agents.sources.rss import Entry, LinkedContent

import trafilatura

MAX_LINKS = 3
MAX_CHARS_PER_LINK = 4000
MIN_CHARS_PER_LINK = 300

_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)

_SKIP_HOST_SUBSTR = ("mail.google.com",)
_SKIP_PATH_SUBSTR = ("unsubscribe", "/opt-out", "/opt_out", "/preferences")
_SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico",
             ".css", ".js", ".pdf", ".zip", ".mp4", ".mp3")
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src",
}


def _clean(url: str) -> str | None:
    try:
        u = urlparse(url.rstrip(".,);"))
    except Exception:
        return None
    if u.scheme not in ("http", "https"):
        return None
    if not u.netloc:
        return None
    if any(s in u.netloc for s in _SKIP_HOST_SUBSTR):
        return None
    low_path = u.path.lower()
    if any(s in low_path for s in _SKIP_PATH_SUBSTR):
        return None
    if any(low_path.endswith(ext) for ext in _SKIP_EXT):
        return None
    cleaned_q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k.lower() not in _TRACKING_PARAMS]
    new_query = "&".join(f"{k}={v}" if v else k for k, v in cleaned_q)
    return urlunparse((u.scheme, u.netloc, u.path.rstrip("/"), "", new_query, ""))


def extract_urls(body: str, entry_url: str) -> list[str]:
    """Return up to MAX_LINKS unique cleaned URLs, one per distinct domain."""
    self_clean = _clean(entry_url)
    seen_domains: set[str] = set()
    if self_clean:
        seen_domains.add(urlparse(self_clean).netloc)
    seen_urls: set[str] = set()
    out: list[str] = []
    for raw in _URL_RE.findall(body or ""):
        cleaned = _clean(raw)
        if not cleaned or cleaned in seen_urls:
            continue
        domain = urlparse(cleaned).netloc
        if domain in seen_domains:
            continue
        seen_domains.add(domain)
        seen_urls.add(cleaned)
        out.append(cleaned)
        if len(out) >= MAX_LINKS:
            break
    return out


def expand_links(entry: Entry) -> Entry:
    urls = extract_urls(entry.summary, entry.url)
    if not urls:
        return entry
    linked: list[LinkedContent] = []
    for url in urls:
        html = _fetch_html(url)
        if not html:
            continue
        try:
            text = trafilatura.extract(
                html, include_comments=False, include_tables=False, favor_recall=True, url=url
            )
        except Exception:
            text = None
        if not text or len(text) < MIN_CHARS_PER_LINK:
            continue
        linked.append(LinkedContent(url=url, text=text[:MAX_CHARS_PER_LINK]))
    entry.linked_contents = linked
    return entry
