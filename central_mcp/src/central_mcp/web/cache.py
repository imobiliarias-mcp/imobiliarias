"""In-memory TTL cache for provider detail payloads (bounded, process-local)."""

from __future__ import annotations

import time
from collections.abc import Callable, Hashable
from typing import Any

DEFAULT_MAX_ENTRIES = 1000


class TtlCache:
    """Stores values for a fixed time-to-live, evicting the oldest when full."""

    def __init__(
        self,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        max_entries: int = DEFAULT_MAX_ENTRIES,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._max_entries = max_entries
        self._entries: dict[Hashable, tuple[float, Any]] = {}

    def get(self, key: Hashable) -> Any | None:
        """Return the live value for key, or None when missing or expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self._clock() - stored_at >= self._ttl:
            del self._entries[key]
            return None
        return value

    def set(self, key: Hashable, value: Any) -> None:
        """Store value under key; a zero TTL disables caching."""
        if self._ttl <= 0:
            return
        if key not in self._entries and len(self._entries) >= self._max_entries:
            self._evict_oldest()
        self._entries[key] = (self._clock(), value)

    def _evict_oldest(self) -> None:
        oldest_key = min(self._entries, key=lambda k: self._entries[k][0])
        del self._entries[oldest_key]
