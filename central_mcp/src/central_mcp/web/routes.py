"""Starlette routes for the browser JSON API and the static single-page UI."""

from __future__ import annotations

import math
from collections.abc import Awaitable, Callable, Mapping
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
from central_mcp.web.ordering import interleave_by_provider

DEFAULT_LIMIT = 60
MAX_LIMIT = 200
FEDERATED_FETCH_LIMIT = 1000
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

    def __init__(self, service: WebSearchService, enricher: ListingEnricher, catalog: CachedCatalog) -> None:
        self._service = service
        self._enricher = enricher
        self._catalog = catalog

    async def providers(self, request: Request) -> Response:
        """List providers with coverage and supported operations (cached, off the event loop)."""
        return JSONResponse(await self._catalog.providers())

    async def facets(self, request: Request) -> Response:
        """Return the taxonomy (cities, neighborhoods, types) of one provider."""
        try:
            payload = await self._service.facets(_required_text(request.query_params, "provider"))
        except (ValueError, KeyError, ProviderError) as exc:
            return _error_response(exc)
        return JSONResponse(payload)

    async def search(self, request: Request) -> Response:
        """Search all or selected providers, spread the page across agencies, attach media."""
        try:
            params = parse_search_params(request.query_params)
            limit = params.pop("limit")
            outcome = await self._service.federated_search(
                **params, include_raw=True, limit=FEDERATED_FETCH_LIMIT
            )
        except (ValueError, KeyError, ProviderError) as exc:
            return _error_response(exc)
        page = interleave_by_provider(outcome["results"], limit)
        listings = await self._enricher.enrich(page)
        return JSONResponse(
            {
                "status": outcome["status"],
                "providers": outcome["providers"],
                "results": [listing.to_dict() for listing in listings],
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


def parse_search_params(query: Mapping[str, str]) -> dict[str, Any]:
    """Translate raw query parameters into validated keyword arguments for federated_search."""
    return {
        "providers": _csv(query.get("providers")),
        "city": _optional_text(query.get("city")),
        "min_price": _optional_float(query.get("min_price"), "min_price"),
        "max_price": _optional_float(query.get("max_price"), "max_price"),
        "bedrooms": _optional_int(query.get("bedrooms"), "bedrooms"),
        "property_type": _optional_text(query.get("property_type")),
        "page": _bounded_int(query.get("page"), "page", default=1, minimum=1, maximum=10_000),
        "limit": _bounded_int(query.get("limit"), "limit", default=DEFAULT_LIMIT, minimum=1, maximum=MAX_LIMIT),
    }


@dataclass(frozen=True)
class WebSurface:
    """Browser API routes plus the startup task that pre-builds their shared data."""

    routes: list[BaseRoute]
    warm_up: Callable[[], Awaitable[None]]


def build_web_routes(service: WebSearchService, config: AppConfig) -> WebSurface:
    """Create /api routes sharing one detail cache, enricher and provider catalog."""
    cache = TtlCache(ttl_seconds=config.detail_cache_ttl_seconds)
    enricher = ListingEnricher(service, cache, concurrency=config.enrich_concurrency)
    catalog = CachedCatalog(service, ttl_seconds=CATALOG_TTL_SECONDS)
    api = WebApi(service, enricher, catalog)
    routes: list[BaseRoute] = [
        Route("/api/providers", api.providers, methods=["GET"]),
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


def _required_text(query: Mapping[str, str], name: str) -> str:
    value = _optional_text(query.get(name))
    if value is None:
        raise ValueError(f"Missing required parameter: {name}")
    return value


def _optional_text(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def _csv(raw: str | None) -> list[str] | None:
    text = _optional_text(raw)
    if text is None:
        return None
    return [part.strip() for part in text.split(",") if part.strip()]


def _optional_float(raw: str | None, name: str) -> float | None:
    text = _optional_text(raw)
    if text is None:
        return None
    try:
        value = float(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def _optional_int(raw: str | None, name: str) -> int | None:
    text = _optional_text(raw)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _bounded_int(raw: str | None, name: str, *, default: int, minimum: int, maximum: int) -> int:
    value = _optional_int(raw, name)
    if value is None:
        return default
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
