"""Fetch the original URL of an Entry and replace `summary` with the extracted
full body. Best-effort: any failure leaves the entry's existing summary intact.

Karpathy 1.2 — minimum viable:
- 5s timeout, no retry
- realistic User-Agent (some sites block default urllib)
- trafilatura for main-content extraction (handles Korean+English well)
- cap extracted body to MAX_CHARS so the next summarize call stays cheap
- skip URLs from gmail.com (forwarded Newsletter body is already inline)
"""
from __future__ import annotations

from urllib.request import Request, urlopen

import trafilatura

from src.agents.sources.rss import Entry

TIMEOUT_S = 5
MAX_CHARS = 8000
MIN_CHARS = 200  # extracted body shorter than this -> treat as failure
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def _fetch_html(url: str) -> str | None:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.9"})
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            data = resp.read()
        # trafilatura accepts bytes; it figures out encoding
        return data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    except Exception:
        return None


def fetch_fulltext(entry: Entry) -> Entry:
    if not entry.url or "mail.google.com" in entry.url:
        return entry
    html = _fetch_html(entry.url)
    if not html:
        return entry
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_recall=True,
        url=entry.url,
    )
    if not text or len(text) < MIN_CHARS:
        return entry
    entry.summary = text[:MAX_CHARS]
    return entry
