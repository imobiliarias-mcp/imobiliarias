"""Attach detail media (photos, description) to search results, failing soft per item."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from central_mcp.errors import ProviderError
from central_mcp.web.cache import TtlCache
from central_mcp.web.listing import WebListing

logger = logging.getLogger(__name__)

RECOVERABLE_ERRORS = (ProviderError, RuntimeError, OSError, ValueError, KeyError, TypeError, AttributeError)

# Total time the search waits for media; slow detail calls are abandoned after this.
DEFAULT_BUDGET_SECONDS = 8.0


class DetailSource(Protocol):
    """Anything able to fetch one provider listing detail (RentalService satisfies it)."""

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        """Return the detail payload for one property."""


class ListingEnricher:
    """Fetches details concurrently for search results, caching successful ones."""

    def __init__(
        self,
        source: DetailSource,
        cache: TtlCache,
        concurrency: int,
        budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    ) -> None:
        self._source = source
        self._cache = cache
        self._concurrency = concurrency
        self._budget_seconds = budget_seconds

    async def enrich(self, projected: list[dict[str, Any]]) -> list[WebListing]:
        """Return web listings in the same order; details still pending at the budget are dropped."""
        semaphore = asyncio.Semaphore(self._concurrency)
        details = await self._details_within_budget(semaphore, projected)
        return [WebListing.from_parts(item, detail) for item, detail in zip(projected, details)]

    async def _details_within_budget(
        self, semaphore: asyncio.Semaphore, projected: list[dict[str, Any]]
    ) -> list[dict[str, Any] | None]:
        if not projected:
            return []
        tasks = [asyncio.create_task(self._detail_for(semaphore, item)) for item in projected]
        done, pending = await asyncio.wait(tasks, timeout=self._budget_seconds)
        await _cancel_and_wait(pending)
        return [task.result() if task in done else None for task in tasks]

    async def _detail_for(self, semaphore: asyncio.Semaphore, projected: dict[str, Any]) -> dict[str, Any] | None:
        provider = projected.get("provider")
        code = projected.get("code")
        if not provider or not code:
            return None
        key = (provider, code)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        return await self._fetch_and_cache(semaphore, key)

    async def _fetch_and_cache(self, semaphore: asyncio.Semaphore, key: tuple[str, str]) -> dict[str, Any] | None:
        provider, code = key
        try:
            async with semaphore:
                detail = await self._source.detail(provider, code)
        except RECOVERABLE_ERRORS as exc:
            logger.warning("detail enrichment failed for %s/%s: %s", provider, code, exc)
            return None
        self._cache.set(key, detail)
        return detail


async def _cancel_and_wait(tasks: set[asyncio.Task]) -> None:
    """Cancel unfinished detail tasks and wait until they have unwound."""
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
