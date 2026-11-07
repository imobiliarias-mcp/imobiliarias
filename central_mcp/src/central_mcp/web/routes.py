"""Starlette routes for the browser JSON API and the static single-page UI."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles

from central_mcp.application.service import project_listing
from central_mcp.config import AppConfig
from central_mcp.errors import ProviderError
from central_mcp.web.cache import TtlCache
from central_mcp.web.catalog import CachedCatalog
from central_mcp.web.enrichment import ListingEnricher
from central_mcp.web.listing import WebListing
from central_mcp.web.location_catalog import LocationCatalog
from central_mcp.web.result_page import take_page
from central_mcp.web.search_cache import SearchOutcomeCache
from central_mcp.web.search_flow import SearchFlow, is_visible_provider
from central_mcp.web.search_params import parse_search_params, required_text

CATALOG_TTL_SECONDS = 3600
PRICE_KEYS = ("rent_price", "condo_fee", "iptu", "total_price")


class WebSearchService(Protocol):
    """Subset of RentalService used by the browser API."""

    def catalog(self) -> list[dict[str, Any]]: ...

    async def federated_search(self, **kwargs: Any) -> dict[str, Any]: ...

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]: ...

    async def facets(self, provider: str) -> dict[str, Any]: ...


class WebApi:
    """Handlers translating HTTP query/path params into service calls and JSON."""

    def __init__(
        self,
        service: WebSearchService,
        enricher: ListingEnricher,
        catalog: CachedCatalog,
        locations: LocationCatalog,
        search: SearchFlow,
    ) -> None:
        self._service = service
        self._enricher = enricher
        self._catalog = catalog
        self._locations = locations
        self._search = search

    async def providers(self, request: Request) -> Response:
        """List providers with coverage and supported operations (cached, off the event loop)."""
        catalog = await self._catalog.providers()
        return JSONResponse([entry for entry in catalog if is_visible_provider(entry["provider_name"])])

    async def locations(self, request: Request) -> Response:
        """List the cities and neighborhoods observed so far, for the filter controls."""
        return JSONResponse(
            {"cities": self._locations.cities(), "neighborhoods": self._locations.neighborhoods()}
        )

    async def facets(self, request: Request) -> Response:
        """Return the taxonomy (cities, neighborhoods, types) of one provider."""
        try:
            payload = await self._service.facets(required_text(request.query_params, "provider"))
        except (ValueError, KeyError, ProviderError) as exc:
            return _error_response(exc)
        return JSONResponse(payload)

    async def search(self, request: Request) -> Response:
        """Return one page of the ordered search result, enriching only the listings on that page."""
        try:
            params = parse_search_params(request.query_params)
            outcome = await self._search.run(params)
        except (ValueError, KeyError, ProviderError) as exc:
            return _error_response(exc)
        page = take_page(outcome.listings, params["page"], params["limit"])
        listings = await self._enricher.enrich(page.items)
        return JSONResponse(
            {
                "status": outcome.status,
                "providers": outcome.providers,
                "results": [listing.to_dict() for listing in listings],
                "hidden_without_neighborhood": outcome.hidden_without_neighborhood,
                "page": page.page,
                "page_size": page.page_size,
                "total": page.total,
                "has_more": page.has_more,
            }
        )

    async def listing_detail(self, request: Request) -> Response:
        """Return one listing with its full photo gallery, description and prices."""
        provider = request.path_params["provider"]
        code = request.path_params["code"]
        try:
            detail = await self._service.detail(provider, code)
        except (ValueError, KeyError, ProviderError) as exc:
            return _error_response(exc)
        listing = WebListing.from_parts(_detail_projection(provider, code, detail), detail)
        return JSONResponse(listing.to_dict())


@dataclass(frozen=True)
class WebSurface:
    """Browser API routes plus the startup task that pre-builds their shared data."""

    routes: list[BaseRoute]
    warm_up: Callable[[], Awaitable[None]]


def build_web_routes(service: WebSearchService, config: AppConfig) -> WebSurface:
    """Create /api routes sharing one detail cache, enricher, provider catalog and location catalog."""
    detail_cache = TtlCache(ttl_seconds=config.detail_cache_ttl_seconds)
    enricher = ListingEnricher(service, detail_cache, concurrency=config.enrich_concurrency)
    catalog = CachedCatalog(service, ttl_seconds=CATALOG_TTL_SECONDS)
    locations = LocationCatalog.open(config.data_dir)
    search_cache = SearchOutcomeCache(ttl_seconds=config.search_cache_ttl_seconds)
    search = SearchFlow(service, search_cache, locations)
    api = WebApi(service, enricher, catalog, locations, search)
    routes: list[BaseRoute] = [
        Route("/api/providers", api.providers, methods=["GET"]),
        Route("/api/locations", api.locations, methods=["GET"]),
        Route("/api/facets", api.facets, methods=["GET"]),
        Route("/api/search", api.search, methods=["GET"]),
        Route("/api/listings/{provider}/{code}", api.listing_detail, methods=["GET"]),
    ]
    return WebSurface(routes=routes, warm_up=catalog.warm_up)


def build_static_mount(static_dir: str | None) -> Mount | None:
    """Serve the built single-page UI at the root, or nothing when the directory is absent."""
    if static_dir is None or not Path(static_dir).is_dir():
        return None
    return Mount("/", app=StaticFiles(directory=static_dir, html=True), name="web")


def _detail_projection(provider: str, code: str, detail: dict[str, Any]) -> dict[str, Any]:
    projected = project_listing(provider, detail)
    projected["code"] = code
    for key in PRICE_KEYS:
        if detail.get(key) is not None:
            projected[key] = detail[key]
    return projected


def _error_response(exc: Exception) -> JSONResponse:
    if isinstance(exc, ProviderError):
        body = {"error": exc.message, "error_code": exc.code, "provider": exc.provider}
        return JSONResponse(body, status_code=502)
    if isinstance(exc, KeyError):
        return JSONResponse({"error": "Unknown provider"}, status_code=404)
    return JSONResponse({"error": str(exc)}, status_code=400)

