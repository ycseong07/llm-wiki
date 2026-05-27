"""Secret access via Windows Credential Manager (keyring).

Single source for reading secrets. Writes are done by `scripts/setup_credentials.py`.
Falls back to environment variables (uppercase form) for CI/dev convenience.
"""
from __future__ import annotations

import os

import keyring

SERVICE = "llm_wiki"

GEMINI_API_KEY = "gemini_api_key"

KNOWN_KEYS = (GEMINI_API_KEY,)


def get_secret(key: str) -> str | None:
    value = keyring.get_password(SERVICE, key)
    if value:
        return value
    return os.environ.get(key.upper())


def require_secret(key: str) -> str:
    value = get_secret(key)
    if not value:
        raise RuntimeError(
            f"Secret '{key}' not found. Run `uv run python scripts/setup_credentials.py`."
        )
    return value


def set_secret(key: str, value: str) -> None:
    keyring.set_password(SERVICE, key, value)


def delete_secret(key: str) -> None:
    try:
        keyring.delete_password(SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass
