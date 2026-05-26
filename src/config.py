"""Project config — paths only.

Secret loading will go through `src/credentials.py` (keyring) when first needed.
This module deliberately only knows non-secret paths.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VAULT_PATH = Path(os.environ.get("VAULT_PATH", PROJECT_ROOT / "vault"))
