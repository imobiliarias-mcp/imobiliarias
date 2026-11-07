"""Run one search: fetch the providers (cached), then locate, scope, price-filter and order the result."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from central_mcp.providers.capabilities import get_provider_capability
from central_mcp.web.location_catalog import LocationCatalog
from central_mcp.web.location_scope import LocationScope, scope_results
from central_mcp.web.locations import ParsedLocation, parse_location
from central_mcp.web.ordering import order_by_total_price
from central_mcp.web.price_filter import apply_rent_range
from central_mcp.web.search_cache import SearchOutcomeCache

FEDERATED_FETCH_LIMIT = 1000


class FederatedSource(Protocol):
    """Anything that fans a search out to providers (RentalService satisfies it)."""

    async def federated_search(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class SearchOutcome:
    """The whole ordered result of one search, before paging."""

    status: str
    providers: list[dict[str, Any]]
    listings: list[dict[str, Any]]
    hidden_without_neighborhood: int


class SearchFlow:
    """Turns validated search parameters into the ordered listings of the whole result."""

    def __init__(self, service: FederatedSource, cache: SearchOutcomeCache, locations: LocationCatalog) -> None:
        self._service = service
        self._cache = cache
        self._locations = locations

    async def run(self, params: Mapping[str, Any]) -> SearchOutcome:
        """Return the scoped, price-filtered and ordered listings for the validated params."""
        city_name = self._resolved_city(params["city"])
        provider_args = _provider_arguments(params, city_name)
        outcome = await self._cache.get_or_fetch(
            _cache_key(provider_args),
            lambda: self._service.federated_search(**provider_args, page=1, include_raw=True, limit=FEDERATED_FETCH_LIMIT),
            refresh=params["refresh"],
        )
        scope = LocationScope(city_name=city_name, neighborhood_keys=frozenset(params["neighborhoods"] or []))
        scoped = scope_results(self._locate(outcome["results"]), scope, self._locations)
        priced = apply_rent_range(scoped.listings, params["min_price"], params["max_price"])
        ordered = order_by_total_price(priced, descending=params["sort"] == "total_desc")
        providers = [entry for entry in outcome["providers"] if is_visible_provider(entry["provider"])]
        return SearchOutcome(
            status=_overall_status([entry["status"] for entry in providers]),
            providers=providers,
            listings=ordered,
            hidden_without_neighborhood=scoped.hidden_without_neighborhood,
        )

    def _resolved_city(self, requested: str | None) -> str | None:
        if requested is None:
            return None
        return self._locations.resolve_city(requested) or requested

    def _locate(self, results: list[dict[str, Any]]) -> list[tuple[dict[str, Any], ParsedLocation]]:
        """Parse each listing's location, record new places in the catalog, and pair the two."""
        known = [entry["name"] for entry in self._locations.cities()]
        located = [(item, parse_location(item.get("location"), known_cities=known)) for item in results]
        self._locations.observe(parsed for _, parsed in located)
        return located


def _provider_arguments(params: Mapping[str, Any], city_name: str | None) -> dict[str, Any]:
    """Only the filters the providers themselves understand; location and price are applied centrally."""
    return {
        "providers": params["providers"],
        "city": city_name,
        "bedrooms": params["bedrooms"],
        "property_type": params["property_type"],
        "max_price": params["max_price"],
    }


def _cache_key(provider_args: Mapping[str, Any]) -> Hashable:
    providers = provider_args["providers"]
    return (
        None if providers is None else tuple(sorted(providers)),
        provider_args["city"],
        provider_args["bedrooms"],
        provider_args["property_type"],
        provider_args["max_price"],
    )


def is_visible_provider(provider_id: str) -> bool:
    """Hide providers that are disabled in the capability matrix from the browser UI."""
    return get_provider_capability(provider_id).is_available


def _overall_status(statuses: list[str]) -> str:
    """Summarize provider outcomes as ok, error, or partial."""
    if statuses and all(status == "ok" for status in statuses):
        return "ok"
    if not any(status == "ok" for status in statuses):
        return "error"
    return "partial"
