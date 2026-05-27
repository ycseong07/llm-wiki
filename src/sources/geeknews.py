"""GeekNews (news.hada.io) source adapter.

hada.io is an aggregator — each topic page summarizes an external article and
collects Korean comments. We fetch the original article body for scoring, but
still record the meta URL as `source_url` so downstream ingestion in Obsidian
can use the AUTO-APPENDED zone pattern (raw/CLAUDE.md).
"""
from __future__ import annotations

import html as _html
import re
from typing import Iterator
from urllib.parse import urlparse

import feedparser

from src.sources._fulltext import extract_main_text, fetch_html
from src.sources.base import Candidate

RSS_URL = "https://news.hada.io/rss/news"
MAX_PER_FETCH = 20
MIN_BODY_CHARS = 200
MAX_BODY_CHARS = 16000

name = "geeknews"

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]+")
_URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)
_META_HOST = "news.hada.io"


def _clean_summary(text: str, max_chars: int = 3000) -> str:
    if not text:
        return ""
    s = _BR_RE.sub("\n", text)
    s = _TAG_RE.sub(" ", s)
    s = _html.unescape(s)
    s = _WS_RE.sub(" ", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s[:max_chars]


def _first_external_url(text: str) -> str | None:
    for raw in _URL_RE.findall(text or ""):
        url = raw.rstrip(".,);")
        try:
            host = urlparse(url).netloc
        except Exception:
            continue
        if not host or _META_HOST in host:
            continue
        return url
    return None


def fetch() -> Iterator[Candidate]:
    parsed = feedparser.parse(RSS_URL)
    for e in parsed.entries[:MAX_PER_FETCH]:
        meta_url = (e.get("link") or "").strip()
        if not meta_url:
            continue
        title = (e.get("title") or "").strip()
        published = (e.get("published") or "").strip()
        summary = _clean_summary(e.get("summary") or "")

        original_url = _first_external_url(e.get("summary") or "")
        if not original_url:
            meta_html = fetch_html(meta_url)
            if meta_html:
                original_url = _first_external_url(meta_html)

        body = ""
        if original_url:
            orig_html = fetch_html(original_url)
            if orig_html:
                extracted = extract_main_text(orig_html, url=original_url)
                if extracted and len(extracted) >= MIN_BODY_CHARS:
                    body = extracted[:MAX_BODY_CHARS]
        if not body:
            body = summary

        yield Candidate(
            title=title,
            source=name,
            source_url=meta_url,
            body=body,
            published=published,
            summary=summary,
            is_meta=True,
            original_url=original_url,
        )
