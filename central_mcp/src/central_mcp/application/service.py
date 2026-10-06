"""Application service orchestrating rental research and federated queries."""

from __future__ import annotations

import asyncio
from typing import Any

from central_mcp.errors import ProviderError, ProviderErrorCode
from central_mcp.providers.capabilities import (
    get_provider_capability,
    validate_provider_filters,
    validate_search_request,
)
from central_mcp.providers.registry import ProviderRegistry


def project_listing(
    provider: str, item: dict[str, Any], include_raw: bool = False
) -> dict[str, Any]:
    """Transform raw provider listing into standard compact projection."""
    code = item.get("code") or item.get("id") or item.get("property_code")
    title = item.get("title")
    location = _extract_location(item)
    price = _extract_price(item)
    bedrooms = item.get("bedrooms") or item.get("rooms")
    url = item.get("url") or item.get("detail_url")
    projected: dict[str, Any] = {
        "provider": provider,
        "code": str(code) if code is not None else None,
        "title": str(title) if title is not None else None,
        "location": location,
        "price": price,
        "bedrooms": int(bedrooms) if bedrooms is not None else None,
        "url": str(url) if url is not None else None,
    }
    if include_raw:
        projected["raw"] = item
    return projected


def _extract_location(item: dict[str, Any]) -> str | None:
    neigh = item.get("neighborhood")
    city = item.get("city")
    if neigh and city:
        return f"{neigh}, {city}"
    if neigh:
        return str(neigh)
    if city:
        return str(city)
    loc = item.get("location")
    return str(loc) if loc else None


def _extract_price(item: dict[str, Any]) -> Any:
    for key in ("price", "rental_price_formatted", "price_formatted", "rental_price", "price_text"):
        val = item.get(key)
        if val is not None and val != "":
            return val
    return None


class RentalService:
    """Facade orchestrating queries across rental provider adapters."""

    def __init__(self, registry: ProviderRegistry | None = None, concurrency_limit: int = 5) -> None:
        self._registry = registry or ProviderRegistry.create_default()
        self._semaphore = asyncio.Semaphore(concurrency_limit)

    def catalog(self) -> list[dict[str, Any]]:
        return self._registry.catalog().to_list()

    async def search(
        self,
        provider: str,
        city: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        page: int = 1,
        include_raw: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Execute validated search on a specific provider."""
        validate_search_request(city, min_price, max_price, bedrooms, property_type, page)
        filters = {"city": city, "min_price": min_price, "max_price": max_price, "bedrooms": bedrooms, "property_type": property_type}
        validate_provider_filters(provider, filters)
        cap = get_provider_capability(provider)
        if not cap.is_available:
            raise ProviderError(provider, ProviderErrorCode.UNAVAILABLE, cap.unavailable_reason)
        adapter = self._registry.get(provider)
        kwargs = {"city": city or "", "min_price": min_price or 0.0, "max_price": max_price or 0.0, "bedrooms": bedrooms or 0, "property_type": property_type or "", "page": page}
        async with self._semaphore:
            raw = await asyncio.to_thread(adapter.search_rentals, **kwargs)
        raw_listings = raw.get("listings", [])
        projected = [project_listing(provider, x, include_raw) for x in raw_listings]
        return {"status": "ok", "provider": provider, "count": len(projected), "results": projected[:limit], "listings": projected[:limit]}

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        adapter = self._registry.get(provider)
        async with self._semaphore:
            return await asyncio.to_thread(adapter.get_property_detail, property_code)

    async def facets(self, provider: str) -> dict[str, Any]:
        adapter = self._registry.get(provider)
        async with self._semaphore:
            return await asyncio.to_thread(adapter.get_facets)

    async def federated_search(
        self,
        providers: list[str] | None = None,
        city: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        page: int = 1,
        include_raw: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Execute parallel search across multiple providers and aggregate listings."""
        known = set(self._registry.all_provider_ids())
        validate_search_request(
            city, min_price, max_price, bedrooms, property_type, page, providers, known
        )
        target = providers or list(self._registry.all_provider_ids())
        tasks = [self._safe_search(p, city, min_price, max_price, bedrooms, property_type, page, include_raw) for p in target]
        results = await asyncio.gather(*tasks)
        return self._format_federated_response(results, limit)

    async def _safe_search(
        self, provider: str, city: str | None, min_price: float | None, max_price: float | None,
        bedrooms: int | None, property_type: str | None, page: int, include_raw: bool
    ) -> dict[str, Any]:
        try:
            filters = {"city": city, "min_price": min_price, "max_price": max_price, "bedrooms": bedrooms, "property_type": property_type}
            validate_provider_filters(provider, filters)
            cap = get_provider_capability(provider)
            if not cap.is_available:
                return {"provider": provider, "status": "unavailable", "count": 0, "error_code": "unavailable", "error": cap.unavailable_reason, "results": []}
            adapter = self._registry.get(provider)
            kwargs = {"city": city or "", "min_price": min_price or 0.0, "max_price": max_price or 0.0, "bedrooms": bedrooms or 0, "property_type": property_type or "", "page": page}
            async with self._semaphore:
                res = await asyncio.to_thread(adapter.search_rentals, **kwargs)
            listings = res.get("listings", [])
            projected = [project_listing(provider, x, include_raw) for x in listings]
            return {"provider": provider, "status": "ok", "count": len(projected), "error_code": None, "error": None, "results": projected}
        except ProviderError as err:
            return {"provider": provider, "status": "error", "count": 0, "error_code": err.code, "error": err.message, "results": []}
        except Exception as exc:
            return {"provider": provider, "status": "error", "count": 0, "error_code": "upstream_error", "error": str(exc), "results": []}

    def _format_federated_response(self, provider_results: list[dict[str, Any]], limit: int) -> dict[str, Any]:
        all_items: list[dict[str, Any]] = []
        statuses: list[str] = []
        summaries: list[dict[str, Any]] = []
        for r in provider_results:
            statuses.append(r["status"])
            summaries.append({"provider": r["provider"], "status": r["status"], "count": r["count"], "error_code": r["error_code"], "error": r["error"]})
            all_items.extend(r.get("results", []))
        total_ok = statuses.count("ok")
        if total_ok == len(statuses) and total_ok > 0:
            status = "ok"
        elif total_ok == 0:
            status = "error"
        else:
            status = "partial"
        return {"status": status, "providers": summaries, "results": all_items[:limit]}
