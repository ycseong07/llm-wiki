"""Print all labels + counts for the authenticated Gmail account.

Use to diagnose why Gmail fetch returns 0 (label name mismatch, wrong account, etc.).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents.sources.gmail import _build_service  # noqa: E402


def main() -> int:
    service = _build_service()
    profile = service.users().getProfile(userId="me").execute()
    print(f"Authenticated as: {profile.get('emailAddress')}")
    print(f"Total messages in mailbox: {profile.get('messagesTotal')}\n")

    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    print(f"{'id':<25} {'type':<8} {'name'}")
    print("-" * 70)
    for lbl in sorted(labels, key=lambda x: x["name"].lower()):
        full = (
            service.users()
            .labels()
            .get(userId="me", id=lbl["id"])
            .execute()
        )
        count = full.get("messagesTotal", "?")
        print(f"{lbl['id']:<25} {lbl.get('type', '?'):<8} {lbl['name']:<25} ({count} msgs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
