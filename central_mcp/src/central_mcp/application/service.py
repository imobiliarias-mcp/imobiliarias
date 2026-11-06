"""Application service orchestrating rental research and federated queries."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from central_mcp.errors import ProviderError, ProviderErrorCode
from central_mcp.limits import ProviderThrottle
from central_mcp.providers.capabilities import (
    get_provider_capability,
    resolve_city,
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
    rent_price = _parse_numeric_price(price)
    condo_fee = _extract_condo_fee(item)
    iptu = _extract_iptu(item)
    total_price = _calculate_total_price(rent_price, condo_fee, iptu)
    bedrooms = item.get("bedrooms") or item.get("rooms")
    url = item.get("url") or item.get("detail_url")
    projected: dict[str, Any] = {
        "provider": provider,
        "code": str(code) if code is not None else None,
        "title": str(title) if title is not None else None,
        "location": location,
        "price": price,
        "rent_price": rent_price,
        "condo_fee": condo_fee,
        "iptu": iptu,
        "total_price": total_price,
        "bedrooms": int(bedrooms) if bedrooms is not None else None,
        "url": str(url) if url is not None else None,
    }
    if include_raw:
        projected["raw"] = item
    return projected


def _parse_numeric_price(val: Any) -> float | None:
    """Convert price or fee representation into float, or None if absent/invalid."""
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return None
    clean = re.sub(r"[R$\s]", "", val)
    if not clean:
        return None
    return _parse_cleaned_price_string(clean)


def _parse_cleaned_price_string(clean: str) -> float | None:
    """Parse sanitized numeric string into float."""
    try:
        if "," in clean:
            return float(clean.replace(".", "").replace(",", "."))
        if clean.count(".") > 1:
            return float(clean.replace(".", ""))
        if clean.count(".") == 1 and len(clean.split(".")[1]) == 3:
            return float(clean.replace(".", ""))
        return float(clean)
    except (ValueError, TypeError):
        return None


def _extract_condo_fee(item: dict[str, Any]) -> float | None:
    """Extract and normalize condominium fee from listing item."""
    candidate_keys = (
        "condo_fee",
        "condo",
        "monthly_condo",
        "condominium",
        "condominio",
        "valor_condominio",
        "valorcondominio",
        "condominium_price",
        "expenses",
    )
    for key in candidate_keys:
        parsed = _parse_numeric_price(item.get(key))
        if parsed is not None:
            return parsed
    return None


def _extract_iptu(item: dict[str, Any]) -> float | None:
    """Extract and normalize property tax (IPTU) from listing item."""
    candidate_keys = (
        "iptu",
        "monthly_iptu",
        "valoriptu",
        "total_taxes_price",
        "tax",
    )
    for key in candidate_keys:
        parsed = _parse_numeric_price(item.get(key))
        if parsed is not None:
            return parsed
    return None


def _calculate_total_price(
    rent: float | None,
    condo: float | None,
    iptu: float | None = None,
) -> float | None:
    """Calculate combined monthly housing cost."""
    if rent is None:
        return None
    additional_fee = (condo or 0.0) + (iptu or 0.0)
    return round(rent + additional_fee, 2)


def _enrich_detail_pricing(raw: Any) -> Any:
    """Augment detail response with normalized pricing fields."""
    if not isinstance(raw, dict):
        return raw
    price = _extract_price(raw)
    rent_price = _parse_numeric_price(raw.get("rent_price")) or _parse_numeric_price(price)
    condo_fee = _extract_condo_fee(raw)
    iptu = _extract_iptu(raw)
    total_price = _calculate_total_price(rent_price, condo_fee, iptu)
    raw["rent_price"] = rent_price
    raw["condo_fee"] = condo_fee
    raw["iptu"] = iptu
    raw["total_price"] = total_price
    return raw


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


def _validate_property_code(code: str) -> None:
    if not code or not code.strip():
        raise ValueError("Property code cannot be empty")
    if code.startswith(("http://", "https://", "//", "ftp://")):
        raise ValueError("Property code cannot be a URL")
    if any(c in code for c in (" ", "\t", "\n", "\r", "<", ">", '"', "'")):
        raise ValueError("Property code contains invalid characters")


class RentalService:
    """Facade orchestrating queries across rental provider adapters."""

    def __init__(
        self,
        registry: ProviderRegistry | None = None,
        concurrency_limit: int = 5,
        throttle: ProviderThrottle | None = None,
    ) -> None:
        self._registry = registry or ProviderRegistry.create_default()
        self._semaphore = asyncio.Semaphore(concurrency_limit)
        self._throttle = throttle or ProviderThrottle(min_interval_seconds=0.0)

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
        kwargs = {"city": resolve_city(provider, city), "min_price": min_price or 0.0, "max_price": max_price or 0.0, "bedrooms": bedrooms or 0, "property_type": property_type or "", "page": page}
        async with self._semaphore, self._throttle.acquire(provider):
            raw = await asyncio.to_thread(adapter.search_rentals, **kwargs)
        raw_listings = raw.get("listings", [])
        projected = [project_listing(provider, x, include_raw) for x in raw_listings]
        return {"status": "ok", "provider": provider, "count": len(projected), "results": projected[:limit], "listings": projected[:limit]}

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        _validate_property_code(property_code)
        adapter = self._registry.get(provider)
        async with self._semaphore, self._throttle.acquire(provider):
            raw = await asyncio.to_thread(adapter.get_property_detail, property_code)
        return _enrich_detail_pricing(raw)

    async def facets(self, provider: str) -> dict[str, Any]:
        adapter = self._registry.get(provider)
        async with self._semaphore, self._throttle.acquire(provider):
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
            kwargs = {"city": resolve_city(provider, city), "min_price": min_price or 0.0, "max_price": max_price or 0.0, "bedrooms": bedrooms or 0, "property_type": property_type or "", "page": page}
            async with self._semaphore, self._throttle.acquire(provider):
                res = await asyncio.to_thread(adapter.search_rentals, **kwargs)
            listings = res.get("listings", [])
            projected = [project_listing(provider, x, include_raw) for x in listings]
            return {"provider": provider, "status": "ok", "count": len(projected), "error_code": None, "error": None, "results": projected}
        except ProviderError as err:
            return {"provider": provider, "status": "error", "count": 0, "error_code": err.code, "error": err.message, "results": []}
        except (RuntimeError, OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
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
