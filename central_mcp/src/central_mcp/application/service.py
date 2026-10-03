"""Application service orchestrating rental research and federated queries."""

import asyncio
from typing import Any

from central_mcp.providers.registry import ProviderRegistry


class RentalService:
    """Facade orchestrating queries across rental provider adapters."""

    def __init__(self, registry: ProviderRegistry | None = None, concurrency_limit: int = 5) -> None:
        """Initialize service with registry and concurrency limiter."""
        self._registry = registry or ProviderRegistry.create_default()
        self._semaphore = asyncio.Semaphore(concurrency_limit)

    def catalog(self) -> list[dict[str, Any]]:
        """Return catalog of all registered providers and metadata."""
        return self._registry.catalog().to_list()

    async def search(
        self,
        provider: str,
        city: str = "",
        min_price: float = 0.0,
        max_price: float = 0.0,
        bedrooms: int = 0,
        property_type: str = "",
        page: int = 1,
    ) -> dict[str, Any]:
        """Execute search on a specific provider."""
        adapter = self._registry.get(provider)
        kwargs = {
            "city": city,
            "min_price": min_price,
            "max_price": max_price,
            "bedrooms": bedrooms,
            "property_type": property_type,
            "page": page,
        }
        async with self._semaphore:
            return await asyncio.to_thread(adapter.search_rentals, **kwargs)

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        """Execute property detail retrieval on a specific provider."""
        adapter = self._registry.get(provider)
        async with self._semaphore:
            return await asyncio.to_thread(adapter.get_property_detail, property_code)

    async def facets(self, provider: str) -> dict[str, Any]:
        """Execute search facets retrieval on a specific provider."""
        adapter = self._registry.get(provider)
        async with self._semaphore:
            return await asyncio.to_thread(adapter.get_facets)

    async def federated_search(
        self,
        providers: list[str] | None = None,
        city: str = "",
        min_price: float = 0.0,
        max_price: float = 0.0,
        bedrooms: int = 0,
        property_type: str = "",
        page: int = 1,
    ) -> dict[str, Any]:
        """Execute parallel search across multiple providers and aggregate listings."""
        target_providers = providers or list(self._registry.all_provider_ids())
        tasks = [
            self._safe_search(p, city, min_price, max_price, bedrooms, property_type, page)
            for p in target_providers
        ]
        results = await asyncio.gather(*tasks)
        return self._aggregate_results(results)

    async def _safe_search(self, provider: str, *args: Any) -> dict[str, Any]:
        """Safely invoke search on a provider without failing the entire batch."""
        try:
            return await self.search(provider, *args)
        except (RuntimeError, OSError, ValueError, KeyError) as error:
            return {"provider": provider, "status": "error", "error": str(error), "listings": []}


    def _aggregate_results(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Combine and summarize results from multiple providers."""
        all_listings: list[dict[str, Any]] = []
        for res in results:
            listings = res.get("listings", [])
            all_listings.extend(listings)
        return {
            "total_results": len(all_listings),
            "providers_queried": len(results),
            "results": all_listings,
        }
