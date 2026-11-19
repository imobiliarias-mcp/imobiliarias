"""Persistent record of when each listing was first seen.

Writes are atomic (temporary file, then rename). When the data directory is not writable
the store keeps working in memory and logs a warning.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

FIRST_SEEN_FILE_NAME = "first_seen.json"


class FirstSeenStore:
    """Thread-safe registry of (provider, code) -> first_seen_at ISO-8601 UTC timestamp."""

    def __init__(self, path: Path | None, entries: dict[str, str]) -> None:
        self._path = path
        self._entries = entries
        self._persistent = path is not None
        self._lock = threading.Lock()

    @classmethod
    def open(cls, data_dir: Path | None) -> FirstSeenStore:
        """Load from data_dir; fallback to memory-only if absent or not writable."""
        if data_dir is None or not _prepare_directory(data_dir):
            return cls(None, {})
        path = data_dir / FIRST_SEEN_FILE_NAME
        entries = _read_entries(path)
        return cls(path, entries)

    @property
    def is_persistent(self) -> bool:
        """Whether observations are written to disk."""
        return self._persistent

    def observe(self, provider: str, code: str) -> str:
        """Record listing if unseen; return its first_seen_at ISO-8601 timestamp."""
        if not provider or not code or not str(code).strip():
            return ""
        with self._lock:
            return self._observe_locked(provider, code)

    def _observe_locked(self, provider: str, code: str) -> str:
        key = f"{provider}/{code}"
        if key in self._entries:
            return self._entries[key]
        timestamp = _utcnow_iso()
        self._entries[key] = timestamp
        self._save()
        return timestamp

    def observe_many(self, items: Iterable[tuple[str, str]]) -> dict[tuple[str, str], str]:
        """Record multiple listings in one atomic write; return mapping of (provider, code) -> timestamp."""
        with self._lock:
            return self._observe_many_locked(items)

    def _observe_many_locked(self, items: Iterable[tuple[str, str]]) -> dict[tuple[str, str], str]:
        now = _utcnow_iso()
        registered = [self._register(provider, code, now) for provider, code in items if provider and code and str(code).strip()]
        self._save_if_dirty(any(registered))
        return {
            (provider, code): self._entries[f"{provider}/{code}"]
            for provider, code in items
            if provider and code and f"{provider}/{code}" in self._entries
        }

    def _register(self, provider: str, code: str, timestamp: str) -> bool:
        key = f"{provider}/{code}"
        if key in self._entries:
            return False
        self._entries[key] = timestamp
        return True

    def _save_if_dirty(self, dirty: bool) -> None:
        if not dirty:
            return
        self._save()

    def get(self, provider: str, code: str) -> str | None:
        """Return the recorded timestamp, or None."""
        if not provider or not code:
            return None
        key = f"{provider}/{code}"
        with self._lock:
            return self._entries.get(key)

    def _save(self) -> None:
        if self._path is None:
            return
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(self._entries, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self._path)
        except OSError as exc:
            logger.warning("first_seen store not persisted, keeping it in memory: %s", exc)
            self._persistent = False


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _prepare_directory(data_dir: Path) -> bool:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("first_seen directory unavailable, using memory only: %s", exc)
        return False
    if not os.access(data_dir, os.W_OK):
        logger.warning("first_seen directory is not writable, using memory only: %s", data_dir)
        return False
    return True


def _read_entries(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("ignoring unreadable first_seen file %s: %s", path, exc)
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(k): str(v) for k, v in loaded.items() if isinstance(k, str) and isinstance(v, str)}
