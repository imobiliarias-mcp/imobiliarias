"""Shared cache of raw federated search outcomes, with single-flight fan-out per key.

Concurrent requests for the same key await one fetch. The fetch runs as its own task, shielded
from its callers, so a client disconnect does not abort the fan-out that others are waiting on.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Hashable
from typing import Any

from central_mcp.web.cache import TtlCache

DEFAULT_MAX_ENTRIES = 6

Fetch = Callable[[], Awaitable[dict[str, Any]]]


class SearchOutcomeCache:
    """Reuses successful federated outcomes for a time-to-live; never stores error outcomes."""

    def __init__(
        self,
        ttl_seconds: float,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = TtlCache(ttl_seconds=ttl_seconds, clock=clock, max_entries=max_entries)
        self._in_flight: dict[Hashable, asyncio.Task[dict[str, Any]]] = {}

    async def get_or_fetch(self, key: Hashable, fetch: Fetch, refresh: bool = False) -> dict[str, Any]:
        """Return the cached outcome for key, or run fetch once for all concurrent callers.

        refresh skips a stored entry; it still joins a fetch already in flight for the key.
        """
        if not refresh:
            cached = self._store.get(key)
            if cached is not None:
                return cached
        task = self._in_flight.get(key)
        if task is None:
            task = self._start(key, fetch)
        return await asyncio.shield(task)

    def _start(self, key: Hashable, fetch: Fetch) -> asyncio.Task[dict[str, Any]]:
        task = asyncio.ensure_future(self._run(key, fetch))
        self._in_flight[key] = task
        task.add_done_callback(lambda finished: self._finish(key, finished))
        return task

    async def _run(self, key: Hashable, fetch: Fetch) -> dict[str, Any]:
        outcome = await fetch()
        if outcome.get("status") != "error":
            self._store.set(key, outcome)
        return outcome

    def _finish(self, key: Hashable, task: asyncio.Task[dict[str, Any]]) -> None:
        """Forget the fetch once done, even when it failed or was cancelled, and mark any failure retrieved."""
        if self._in_flight.get(key) is task:
            del self._in_flight[key]
        if not task.cancelled():
            task.exception()
