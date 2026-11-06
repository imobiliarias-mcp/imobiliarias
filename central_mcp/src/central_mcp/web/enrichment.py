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


class DetailSource(Protocol):
    """Anything able to fetch one provider listing detail (RentalService satisfies it)."""

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        """Return the detail payload for one property."""


class ListingEnricher:
    """Fetches details concurrently for search results, caching successful ones."""

    def __init__(self, source: DetailSource, cache: TtlCache, concurrency: int) -> None:
        self._source = source
        self._cache = cache
        self._concurrency = concurrency

    async def enrich(self, projected: list[dict[str, Any]]) -> list[WebListing]:
        """Return web listings in the same order, each with media when available."""
        semaphore = asyncio.Semaphore(self._concurrency)
        return list(await asyncio.gather(*(self._enrich_one(semaphore, item) for item in projected)))

    async def _enrich_one(self, semaphore: asyncio.Semaphore, projected: dict[str, Any]) -> WebListing:
        detail = await self._detail_for(semaphore, projected)
        return WebListing.from_parts(projected, detail)

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
