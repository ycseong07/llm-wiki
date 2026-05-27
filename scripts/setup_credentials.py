"""Interactive setup for Windows Credential Manager secrets.

Run: `uv run python scripts/setup_credentials.py`

Prompts for each known secret. Enter blank to skip (keeps existing value).
Type 'delete' to remove a stored value.
"""
from __future__ import annotations

import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import credentials as c  # noqa: E402


PROMPTS = [
    (c.GEMINI_API_KEY, "Gemini API key (required for filter scoring)", True),
]


def main() -> int:
    print(f"Storing secrets under Windows Credential Manager service='{c.SERVICE}'.")
    print("Press Enter to skip a field (keeps existing). Type 'delete' to remove.\n")

    for key, label, required in PROMPTS:
        existing = c.get_secret(key)
        status = "set" if existing else "not set"
        marker = "(required)" if required else "(optional)"
        print(f"[{status}] {key} {marker} — {label}")
        value = getpass("  > ").strip()

        if not value:
            if required and not existing:
                print(f"  WARNING: {key} is required and not set. Re-run to provide.")
            continue

        if value.lower() == "delete":
            c.delete_secret(key)
            print(f"  Deleted {key}.")
            continue

        c.set_secret(key, value)
        print(f"  Saved {key}.")

    print("\nDone. Read via `src.credentials.get_secret(key)`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
