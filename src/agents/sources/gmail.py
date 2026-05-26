"""Gmail Newsletter fetcher (readonly).

Yields Entry objects from messages with the Newsletter label.
Refresh token is read from keyring (set by `scripts/gmail_first_auth.py`).
Scope is `gmail.readonly` per CLAUDE.md §2.4 — no label modification.
"""
from __future__ import annotations

import json
from base64 import urlsafe_b64decode
from pathlib import Path
from typing import Iterator

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from src import credentials as c
from src.agents.sources.rss import Entry

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
NEWSLETTER_LABEL = "Newsletter"
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
GCP_DIR = PROJECT_ROOT / "gcp_credentials"


def _client_config() -> dict:
    matches = sorted(GCP_DIR.glob("client_secret_*.json"))
    if not matches:
        raise FileNotFoundError(f"No client_secret_*.json in {GCP_DIR}")
    return json.loads(matches[0].read_text(encoding="utf-8"))["installed"]


def _build_service():
    cfg = _client_config()
    creds = Credentials(
        token=None,
        refresh_token=c.require_secret(c.GMAIL_REFRESH_TOKEN),
        token_uri=cfg["token_uri"],
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_body(payload: dict) -> str:
    plain, html = "", ""
    stack = [payload]
    while stack:
        part = stack.pop()
        data = part.get("body", {}).get("data")
        if data:
            text = urlsafe_b64decode(data).decode("utf-8", errors="replace")
            mime = part.get("mimeType", "")
            if mime == "text/plain" and not plain:
                plain = text
            elif mime == "text/html" and not html:
                html = text
        stack.extend(part.get("parts", []))
    return plain or html


def _sender_name(from_header: str) -> str:
    # "Some Sender <a@b.com>" -> "Some Sender". Falls back to email if no name.
    if "<" in from_header:
        name = from_header.split("<")[0].strip().strip('"')
        if name:
            return name
    return from_header.strip().strip("<>")


def fetch_recent(max_results: int = 50) -> Iterator[Entry]:
    service = _build_service()
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    label_id = next((lbl["id"] for lbl in labels if lbl["name"] == NEWSLETTER_LABEL), None)
    if not label_id:
        return

    resp = (
        service.users()
        .messages()
        .list(userId="me", labelIds=[label_id], maxResults=max_results)
        .execute()
    )
    for ref in resp.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=ref["id"], format="full")
            .execute()
        )
        headers = msg["payload"].get("headers", [])
        yield Entry(
            category="newsletter",
            source=_sender_name(_header(headers, "From")) or "unknown",
            title=_header(headers, "Subject") or "(no subject)",
            url=f"https://mail.google.com/mail/u/0/#inbox/{ref['id']}",
            published=_header(headers, "Date"),
            summary=_decode_body(msg["payload"])[:5000],
        )
