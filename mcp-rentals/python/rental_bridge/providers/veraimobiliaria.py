"""Central bridge adapter for Vera Imobiliária."""

import json
from dataclasses import asdict
from typing import Any
from urllib.parse import urlsplit

from vera_research.client import VeraRentalClient
from vera_research.collaborators import RentalNetworkGateway
from vera_research.domain.criteria import SearchCriteria
from vera_research.domain.enums import PropertyType
from vera_research.infrastructure.http_client import HttpResponse
from vera_research.infrastructure.url_builder import VeraUrlBuilder

from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "veraimobiliaria"
PUBLIC_BASE = "https://www.veraimobiliaria.com.br"


class SafeTransport:
    """Restrict requests to Vera's public search, property, and facet routes."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        parsed = urlsplit(url)
        allowed_path = parsed.path.startswith("/imoveis/") or parsed.path.startswith("/imovel/")
        if parsed.scheme != "https" or parsed.hostname != "www.veraimobiliaria.com.br" or not allowed_path:
            raise ValueError("Unexpected Vera portal target")
        response = ensure_response(self._client.get(url, headers=headers))
        _require_html(response)
        return HttpResponse(response.status_code, response.text, str(response.url))

    def post(self, url: str, data: dict[str, str] | None = None) -> HttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "www.veraimobiliaria.com.br" or parsed.path != "/asp/ajax/bairros2.asp":
            raise ValueError("Unexpected Vera neighborhood target")
        response = ensure_response(self._client.post(url, data=data))
        _require_html(response)
        return HttpResponse(response.status_code, response.text, str(response.url))


def _require_html(response: Any) -> None:
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type:
        raise ValueError("Unexpected non-HTML Vera response")


def _criteria(arguments: dict[str, Any]) -> SearchCriteria:
    return SearchCriteria.create_rental(
        city_id=arguments.get("city_id", 1),
        property_type=PropertyType(arguments.get("property_type", 0)),
        neighborhood_id=arguments.get("neighborhood_id"),
        bedrooms=arguments.get("bedrooms"),
        max_price=arguments.get("max_price"),
        min_price=arguments.get("min_price"),
        page=arguments.get("page", 1),
    )


def _service(client: Any) -> VeraRentalClient:
    gateway = RentalNetworkGateway(http_client=SafeTransport(client), url_builder=VeraUrlBuilder())
    return VeraRentalClient(gateway=gateway)


def _listing_native(item: Any) -> dict[str, Any]:
    return {
        "identity": {"property_id": item.identity.property_id, "url_path": item.identity.url_path, "url": safe_url(item.identity.url, PROVIDER)},
        "title": item.title,
        "location": asdict(item.location),
        "price_text": item.price_text,
        "price_numeric": item.price_numeric,
        "specs": asdict(item.specs),
        "thumbnail_url": item.thumbnail_url,
    }


def _listing_display(item: Any) -> dict[str, Any]:
    location = item.location
    return {
        "reference": item.identity.property_id,
        "url": safe_url(item.identity.url, PROVIDER),
        "title": item.title,
        "location": ", ".join(value for value in (location.neighborhood, location.city, location.state) if value),
        "price": item.price_text or None,
    }


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _service(client).search(_criteria(arguments))
    native_items = [_listing_native(item) for item in result]
    return {
        "native": {"items": native_items, "current_page": result.current_page, "has_next_page": result.has_next_page},
        "display": [_listing_display(item) for item in result],
    }


def _detail_native(detail: Any) -> dict[str, Any]:
    return {
        "overview": asdict(detail.overview),
        "pricing": asdict(detail.pricing),
        "location": asdict(detail.location),
        "specs": asdict(detail.specs),
        "features": list(detail.features),
        "photos": asdict(detail.photos),
        "canonical_url": safe_url(detail.canonical_url, PROVIDER),
    }


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    reference = arguments["reference"]
    safe_url(VeraUrlBuilder().build_detail_url(reference), PROVIDER)
    detail = _service(client).get_details(reference)
    native = _detail_native(detail)
    location = detail.location
    display = {
        "reference": detail.overview.property_id,
        "url": native["canonical_url"],
        "title": detail.overview.title,
        "location": ", ".join(value for value in (location.neighborhood, location.city, location.state) if value),
        "price": detail.pricing.formatted_text or None,
    }
    return {"native": native, "display": [display]}


def _city_data(client: Any) -> list[dict[str, Any]]:
    return [{"city_id": item.numeric_id, "name": item.name} for item in _service(client).get_cities().cities]


def _neighborhood_data(client: Any, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    catalog = _service(client).get_neighborhoods(
        city_id=arguments["city_id"], property_type=arguments.get("property_type", 0)
    )
    return [{"neighborhood_id": item.numeric_id, "name": item.name} for item in catalog.items]


def _facets(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    selector = arguments["selector"]
    native: dict[str, Any] = {}
    if selector in {"cities", "all"}:
        native["cities"] = _city_data(client)
    if selector in {"neighborhoods", "all"}:
        native["neighborhoods"] = _neighborhood_data(client, arguments)
    display = [{"title": item["name"]} for items in native.values() for item in items]
    return {"native": native, "display": display}


def _validate_facets(arguments: dict[str, Any]) -> None:
    selector = arguments.get("selector")
    if selector not in {"cities", "neighborhoods", "all"}:
        raise ValueError("facets requires a supported selector")
    if selector in {"neighborhoods", "all"} and "city_id" not in arguments:
        raise ValueError("neighborhood facets require city_id")
    if arguments.get("transaction_type", 1) != 1:
        raise ValueError("Vera neighborhood facets use rental transaction type 1")


def _validate(operation: str, arguments: dict[str, Any]) -> None:
    allowed = {
        "search": {"city_id", "property_type", "neighborhood_id", "bedrooms", "min_price", "max_price", "page"},
        "detail": {"reference"}, "facets": {"selector", "city_id", "transaction_type", "property_type"},
    }
    if operation not in allowed or not isinstance(arguments, dict) or set(arguments) - allowed[operation]:
        raise ValueError("Invalid operation or arguments")
    if operation == "detail" and not arguments.get("reference", "").isdigit():
        raise ValueError("detail requires a numeric property ID")
    if operation == "facets":
        _validate_facets(arguments)


def _run(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facets(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute a Vera search, property detail, or selected facet query."""
    _validate(operation, arguments)
    if client is not None:
        return json.loads(json.dumps(_run(operation, arguments, client), allow_nan=False))
    with managed_httpx(timeout=20.0) as managed_client:
        return json.loads(json.dumps(_run(operation, arguments, managed_client), allow_nan=False))
