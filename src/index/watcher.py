"""Watchdog handler: vault .md changes -> debounced incremental Qdrant upsert.

Obsidian saves can fire multiple events per save; the debounce coalesces them
into one index_file call ~DEBOUNCE_S after the last event for a given path.
"""
from __future__ import annotations

import threading
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler

from src.index.indexer import index_file
from src.index.qdrant import delete_by_vault_path, ensure_collection

DEBOUNCE_S = 1.0


class VaultHandler(FileSystemEventHandler):
    def __init__(self) -> None:
        super().__init__()
        ensure_collection()
        self._timers: dict[Path, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, path: Path, action: callable) -> None:
        with self._lock:
            existing = self._timers.pop(path, None)
            if existing:
                existing.cancel()
            t = threading.Timer(DEBOUNCE_S, lambda: self._run(path, action))
            t.daemon = True
            self._timers[path] = t
            t.start()

    def _run(self, path: Path, action: callable) -> None:
        with self._lock:
            self._timers.pop(path, None)
        try:
            action(path)
            print(f"[watcher] {action.__name__}: {path.name}")
        except Exception as e:
            print(f"[watcher] error {path.name}: {e!r}")

    def _is_md(self, event: FileSystemEvent) -> bool:
        return not event.is_directory and str(event.src_path).endswith(".md")

    def on_created(self, event: FileSystemEvent) -> None:
        if self._is_md(event):
            self._schedule(Path(event.src_path), index_file)

    def on_modified(self, event: FileSystemEvent) -> None:
        if self._is_md(event):
            self._schedule(Path(event.src_path), index_file)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if self._is_md(event):
            self._schedule(Path(event.src_path), delete_by_vault_path)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory and str(event.src_path).endswith(".md"):
            self._schedule(Path(event.src_path), delete_by_vault_path)
        if not event.is_directory and str(event.dest_path).endswith(".md"):
            self._schedule(Path(event.dest_path), index_file)
