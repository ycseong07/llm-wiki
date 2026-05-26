"""One-shot Gmail OAuth: opens browser, captures refresh token, saves to keyring.

Run once on Windows: `uv run python scripts/gmail_first_auth.py`

After this, all Gmail fetches reconstruct credentials from the keyring-stored
refresh token + the client config in gcp_credentials/. Scope is readonly
(CLAUDE.md §2.4) — message processing is tracked locally, not via labels.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: E402

from src import credentials as c  # noqa: E402

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
GCP_DIR = Path(__file__).resolve().parent.parent / "gcp_credentials"


def find_client_secret() -> Path:
    matches = sorted(GCP_DIR.glob("client_secret_*.json"))
    if not matches:
        raise FileNotFoundError(
            f"No client_secret_*.json in {GCP_DIR}. Download from GCP Console "
            "(OAuth client → Desktop app)."
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple client_secret_*.json found — keep only one: {[str(p) for p in matches]}"
        )
    return matches[0]


def main() -> int:
    secrets_path = find_client_secret()
    print(f"Using OAuth client: {secrets_path.name}")
    print("A browser window will open. Sign in with the Google account whose Gmail you want to ingest.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_path), SCOPES)
    creds = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        prompt="consent",
        open_browser=True,
    )

    if not creds.refresh_token:
        print("ERROR: No refresh_token returned. Revoke any existing grant at "
              "https://myaccount.google.com/permissions and re-run.", file=sys.stderr)
        return 1

    c.set_secret(c.GMAIL_REFRESH_TOKEN, creds.refresh_token)
    print(f"\nSaved refresh token to Windows Credential Manager "
          f"(service='{c.SERVICE}', key='{c.GMAIL_REFRESH_TOKEN}').")
    print("Scopes granted:", creds.scopes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
