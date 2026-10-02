"""Central bridge adapter for Nilton Corretor de Imóveis."""

import json
from dataclasses import asdict
from typing import Any
from urllib.parse import urlsplit

from nilton_research.client import NiltonRentalClient
from nilton_research.collaborators import RentalNetworkGateway
from nilton_research.domain.criteria import (
    FeatureBundle,
    FilterBundle,
    LocationCriteria,
    RoomCriteria,
    SearchCriteria,
    SearchScope,
)
from nilton_research.domain.enums import PropertyType, SortOrder
from nilton_research.domain.values import AreaRange, PageNumber, PriceRange, RoomCount
from nilton_research.infrastructure.http_client import HttpResponse
from nilton_research.infrastructure.url_builder import UrlBuilder

from rental_bridge.providers.niltoncorretordeimoveis_validation import validate
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "niltoncorretordeimoveis"
PUBLIC_BASE = "https://niltoncorretordeimoveis.com.br"


class SafeTransport:
    """Adapt a centrally owned client to Nilton's HTTP response protocol."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        target = urlsplit(url)
        if target.scheme != "https" or target.hostname not in {"niltoncorretordeimoveis.com.br", "www.niltoncorretordeimoveis.com.br"}:
            raise ValueError("Unexpected Nilton portal target")
        if not target.path.startswith("/imovel/"):
            raise ValueError("Unexpected Nilton portal route")
        response = ensure_response(self._client.get(url, headers=headers))
        if "text/html" not in response.headers.get("content-type", "").lower():
            raise ValueError("Unexpected non-HTML Nilton response")
        return HttpResponse(response.status_code, response.text, str(response.url), dict(response.headers))


def _room(arguments: dict[str, Any], name: str, minimum: bool) -> RoomCount | None:
    count = arguments.get(name)
    if count is None:
        return None
    return RoomCount(count, is_minimum=minimum)


def _location(arguments: dict[str, Any]) -> LocationCriteria:
    return LocationCriteria(
        city_slug=arguments.get("city", "timoteo"),
        neighborhood_ids=tuple(arguments.get("neighborhood_ids", [])),
    )


def _rooms(arguments: dict[str, Any]) -> RoomCriteria:
    return RoomCriteria(
        bedrooms=_room(arguments, "bedrooms", arguments.get("min_bedrooms", False)),
        suites=_room(arguments, "suites", arguments.get("min_suites", False)),
        bathrooms=_room(arguments, "bathrooms", arguments.get("min_bathrooms", False)),
        parking_spaces=_room(arguments, "parking_spaces", arguments.get("min_parking_spaces", False)),
    )


def _criteria(arguments: dict[str, Any]) -> SearchCriteria:
    filters = FilterBundle(
        price_range=PriceRange(arguments.get("min_price"), arguments.get("max_price")),
        area_range=AreaRange(arguments.get("min_area"), arguments.get("max_area")),
    )
    return SearchCriteria(
        scope=SearchScope(property_type=PropertyType(arguments.get("property_type", "todos"))),
        location=_location(arguments), filters=filters,
        features=FeatureBundle(room_criteria=_rooms(arguments)),
        sort_order=SortOrder(arguments.get("sort", "")),
        page=PageNumber(arguments.get("page", 1)),
        reference_code=arguments.get("reference_code"),
    )


def _service(client: Any) -> NiltonRentalClient:
    gateway = RentalNetworkGateway(http_client=SafeTransport(client), url_builder=UrlBuilder(PUBLIC_BASE))
    return NiltonRentalClient(gateway=gateway, public_base_url=PUBLIC_BASE)


def _display_listing(item: Any) -> dict[str, Any]:
    return {
        "reference": item.identity.property_id,
        "url": item.url,
        "title": item.title,
        "location": ", ".join(value for value in (item.location.neighborhood, item.location.city, item.location.state) if value),
        "price": item.price_text or None,
    }


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _service(client).search(_criteria(arguments))
    native = result.to_dictionary()
    return {"native": native, "display": [_display_listing(item) for item in result]}


def _detail_native(detail: Any) -> dict[str, Any]:
    return {
        "overview": asdict(detail.overview),
        "pricing": asdict(detail.pricing),
        "location": asdict(detail.location),
        "specs": asdict(detail.specs),
        "gallery": list(detail.gallery),
    }


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    reference = arguments["reference"]
    safe_url(UrlBuilder(PUBLIC_BASE).build_detail_url(reference), PROVIDER)
    detail = _service(client).get_details(reference)
    native = _detail_native(detail)
    overview = detail.overview
    location = detail.location
    display = {
        "reference": overview.property_id,
        "url": safe_url(overview.canonical_url, PROVIDER),
        "title": overview.title,
        "location": ", ".join(value for value in (location.neighborhood, location.city, location.state) if value),
        "price": detail.pricing.formatted or None,
    }
    return {"native": native, "display": [display]}


def _facet_data(catalog: Any) -> dict[str, Any]:
    return {
        "cities": [
            {"name": city.name, "slug": city.slug,
             "neighborhoods": [{"name": item.name, "slug": item.slug, "id": item.numeric_id} for item in city.neighborhoods]}
            for city in catalog
        ]
    }


def _facet_result(native: dict[str, Any], selector: str) -> dict[str, Any]:
    if selector == "locations":
        return native
    return {"cities": native["cities"]}


def _facets(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    native = _facet_data(_service(client).get_locations())
    city_values = native["cities"]
    selector = arguments.get("selector", "locations")
    display = [{"title": city["name"], "location": city["name"]} for city in city_values]
    return {"native": _facet_result(native, selector), "display": display}



def _run(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facets(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute search, detail, or facets using the source's parsed domain models."""
    validate(operation, arguments)
    if client is not None:
        return json.loads(json.dumps(_run(operation, arguments, client), allow_nan=False))
    with managed_httpx(timeout=20.0) as managed_client:
        return json.loads(json.dumps(_run(operation, arguments, managed_client), allow_nan=False))
