"""Provider catalog for the browser API, built off the event loop and cached.

RentalService.catalog() queries every provider adapter synchronously, which spawns
subprocesses. Calling it on the event loop blocks all requests, so it runs in a
worker thread and its result is cached (the catalog is effectively static).
"""

from __future__ import annotations

import asyncio
from typing import Any, Protocol

from central_mcp.web.cache import TtlCache

CATALOG_KEY = "catalog"


class CatalogSource(Protocol):
    """Anything exposing the blocking provider catalog (RentalService satisfies it)."""

    def catalog(self) -> list[dict[str, Any]]:
        """Return provider metadata; may block while probing adapters."""


class CachedCatalog:
    """Serves the provider catalog without blocking the event loop."""

    def __init__(self, source: CatalogSource, ttl_seconds: float) -> None:
        self._source = source
        self._cache = TtlCache(ttl_seconds=ttl_seconds)
        self._lock = asyncio.Lock()

    async def providers(self) -> list[dict[str, Any]]:
        """Return the catalog, building it at most once per TTL even under concurrency."""
        cached = self._cache.get(CATALOG_KEY)
        if cached is not None:
            return cached
        async with self._lock:
            return await self._build_once()

    async def _build_once(self) -> list[dict[str, Any]]:
        cached = self._cache.get(CATALOG_KEY)
        if cached is not None:
            return cached
        built = await asyncio.to_thread(self._source.catalog)
        self._cache.set(CATALOG_KEY, built)
        return built
