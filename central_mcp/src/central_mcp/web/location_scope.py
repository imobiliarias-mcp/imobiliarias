"""Narrow federated results to a city and neighborhoods, annotating each listing with its location.

Listings from providers that report no location inherit the city they were queried for,
so a city filter does not drop agencies that simply omit it. With a neighborhood filter,
listings lacking a neighborhood are excluded and counted, so the UI can say why.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from central_mcp.web.location_catalog import LocationCatalog
from central_mcp.web.locations import ParsedLocation, location_key

TRANSACTION_RENT = "rent"


@dataclass(frozen=True)
class LocationScope:
    """The city and neighborhood keys the caller asked for; empty means no restriction."""

    city_name: str | None
    neighborhood_keys: frozenset[str]


@dataclass(frozen=True)
class ScopedResults:
    """Listings inside the scope, plus how many were hidden for lacking a neighborhood."""

    listings: list[dict[str, Any]]
    hidden_without_neighborhood: int


def scope_results(
    located: Iterable[tuple[dict[str, Any], ParsedLocation]],
    scope: LocationScope,
    catalog: LocationCatalog,
) -> ScopedResults:
    """Keep listings in scope and attach city, neighborhood and transaction to each one."""
    listings: list[dict[str, Any]] = []
    hidden = 0
    for item, parsed in located:
        city = _canonical_city(parsed.city, catalog) or scope.city_name
        if not _city_admitted(city, scope.city_name):
            continue
        if not scope.neighborhood_keys:
            listings.append(_annotate(item, city, parsed.neighborhood, catalog))
            continue
        if parsed.neighborhood is None:
            hidden += 1
            continue
        if _neighborhood_key(city, parsed.neighborhood, catalog) in scope.neighborhood_keys:
            listings.append(_annotate(item, city, parsed.neighborhood, catalog))
    return ScopedResults(listings=listings, hidden_without_neighborhood=hidden)


def _canonical_city(raw: str | None, catalog: LocationCatalog) -> str | None:
    if raw is None:
        return None
    return catalog.resolve_city(raw) or raw


def _city_admitted(city: str | None, requested: str | None) -> bool:
    if requested is None or city is None:
        return True
    return location_key(city) == location_key(requested)


def _neighborhood_key(city: str | None, neighborhood: str, catalog: LocationCatalog) -> str | None:
    if city is None:
        return None
    return catalog.neighborhood_key(city, neighborhood)


def _annotate(
    item: dict[str, Any],
    city: str | None,
    neighborhood: str | None,
    catalog: LocationCatalog,
) -> dict[str, Any]:
    canonical_neighborhood = _canonical_neighborhood(city, neighborhood, catalog)
    return {
        **item,
        "city": city,
        "neighborhood": canonical_neighborhood,
        "transaction": TRANSACTION_RENT,
    }


def _canonical_neighborhood(city: str | None, neighborhood: str | None, catalog: LocationCatalog) -> str | None:
    if neighborhood is None:
        return None
    if city is None:
        return neighborhood
    return catalog.neighborhood_name(city, neighborhood)
