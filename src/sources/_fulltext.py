"""HTTP fetch + trafilatura body extraction. Shared by source adapters.

Best-effort: every failure returns None so callers can fall back to RSS summary.
"""
from __future__ import annotations

from urllib.request import Request, urlopen

import trafilatura

TIMEOUT_S = 10
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)


def fetch_html(url: str) -> str | None:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.9"})
        with urlopen(req, timeout=TIMEOUT_S) as resp:
            data = resp.read()
        return data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    except Exception:
        return None


def extract_main_text(html: str, *, url: str | None = None) -> str | None:
    try:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_recall=True,
            url=url,
        )
    except Exception:
        return None
    return text if text and text.strip() else None
