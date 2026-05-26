"""Long-running vault watcher.

Run in a dedicated PowerShell (will block):
  uv run python scripts/start_watcher.py

Phase 4 will wrap this in a Windows Service / Task Scheduler entry.
"""
from __future__ import annotations

import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from watchdog.observers import Observer  # noqa: E402

from src.config import VAULT_PATH  # noqa: E402
from src.index.watcher import VaultHandler  # noqa: E402


def main() -> int:
    if not VAULT_PATH.exists():
        print(f"Vault not found: {VAULT_PATH}", file=sys.stderr)
        return 1

    handler = VaultHandler()
    observer = Observer()
    observer.schedule(handler, str(VAULT_PATH), recursive=True)
    observer.start()
    print(f"[watcher] watching {VAULT_PATH} (Ctrl+C to stop)")

    stop = threading_stop_event()
    try:
        while not stop.is_set():
            time.sleep(0.5)
    finally:
        observer.stop()
        observer.join(timeout=5)
        print("[watcher] stopped")
    return 0


def threading_stop_event():
    import threading

    ev = threading.Event()

    def _handler(signum, frame):
        ev.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    return ev


if __name__ == "__main__":
    sys.exit(main())
