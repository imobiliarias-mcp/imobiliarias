"""Central bridge adapter for Viva Real's Glue API and public pages."""

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from vivareal_research.client import VivaRealRentalClient
from vivareal_research.collaborators import VivaRealGateway, VivaRealParserSuite
from vivareal_research.domain.criteria import (
    FilterSpecification,
    LocationSpecification,
    RentalSearchCriteria,
)
from vivareal_research.domain.enums import PropertyType, SortOrder
from vivareal_research.domain.values import AreaRange, PageRequest, PriceRange, RoomFilter
from vivareal_research.infrastructure.http_client import HttpClientProtocol
from vivareal_research.infrastructure.url_builder import VivaRealUrlBuilder
from vivareal_research.parsers.detail_parser import VivaRealDetailParser
from vivareal_research.parsers.search_parser import VivaRealSearchParser

from rental_bridge.providers.vivareal_projection import (
    canonical_detail_url,
    detail_display,
    detail_listing,
    detail_native,
    listing_display,
    listing_native,
    product_price,
    suggestion_coordinate,
)
from rental_bridge.providers.vivareal_validation import validate, validate_listing_payload
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "vivareal"
API_HOST = "glue-api.vivareal.com"
PUBLIC_BASE = "https://www.vivareal.com.br"
HEADERS = {
    "x-domain": ".vivareal.com.br",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, text/html, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


@dataclass
class CapturedResponse:
    """Retain raw response documents so serializers distinguish unknown from zero."""

    json_payload: dict[str, Any] | None = None
    html_document: str = ""


class SafeHttp(HttpClientProtocol):
    """Restrict Glue calls and validate returned payloads before source parsers."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._captured = CapturedResponse()

    def get_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != API_HOST or parsed.path not in {"/v2/listings", "/v4/locations"}:
            raise ValueError("Unexpected Viva Real API target")
        response = ensure_response(self._client.get(url, headers={**HEADERS, **(headers or {})}))
        if "json" not in response.headers.get("content-type", "").lower():
            raise ValueError("Unexpected non-JSON Viva Real API response")
        payload = response.json()
        _validate_api_payload(parsed.path, payload)
        self._captured.json_payload = payload
        return payload

    def captured(self) -> CapturedResponse:
        return self._captured

    def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
        target = safe_url(url, PROVIDER)
        response = ensure_response(self._client.get(target, headers={**HEADERS, **(headers or {})}))
        if "text/html" not in response.headers.get("content-type", "").lower():
            raise ValueError("Unexpected non-HTML Viva Real property response")
        self._captured.html_document = response.text
        return response.text


def _validate_api_payload(path: str, payload: Any) -> None:
    if not isinstance(payload, dict):
        raise TypeError("Unexpected Viva Real API document")
    if path == "/v2/listings":
        validate_listing_payload(payload)
    if path == "/v4/locations" and not isinstance(payload.get("result"), list):
        raise ValueError("Unexpected Viva Real locations response")


def _room_filter(arguments: dict[str, Any], field: str) -> RoomFilter:
    return RoomFilter.from_iterable(arguments.get(field, []))


def _location(arguments: dict[str, Any]) -> LocationSpecification:
    default_location = LocationSpecification.create_timoteo_default()
    location_id = arguments.get("location_id", default_location.location_id.location_id)
    city = arguments.get("city", default_location.city)
    state = arguments.get("state", default_location.state)
    from vivareal_research.domain.values import LocationIdentifier
    return LocationSpecification(location_id=LocationIdentifier(location_id), city=city, state=state)


def _page_request(arguments: dict[str, Any]) -> PageRequest:
    size = arguments.get("size", 30)
    page = arguments.get("page")
    offset = arguments.get("offset")
    if page is not None and offset is not None:
        raise ValueError("Specify either page or aligned offset, not both")
    if offset is not None:
        if offset % size:
            raise ValueError("Viva Real offsets must align to page size")
        page = offset // size + 1
    return PageRequest(page_number=page or 1, page_size=size)


def _criteria(arguments: dict[str, Any]) -> RentalSearchCriteria:
    filters = FilterSpecification(
        property_type=PropertyType(arguments.get("property_type", "ALL")),
        bedrooms=_room_filter(arguments, "bedrooms"),
        bathrooms=_room_filter(arguments, "bathrooms"),
        parking_spaces=_room_filter(arguments, "parking_spaces"),
        price_range=PriceRange(arguments.get("min_price"), arguments.get("max_price")),
        area_range=AreaRange(arguments.get("min_area"), arguments.get("max_area")),
        sort_order=SortOrder(arguments.get("sort", "MOST_RELEVANT")),
        pagination=_page_request(arguments),
    )
    return RentalSearchCriteria(location=_location(arguments), filters=filters)


def _service(client: Any) -> tuple[VivaRealRentalClient, SafeHttp]:
    transport = SafeHttp(client)
    builder = VivaRealUrlBuilder()
    parsers = VivaRealParserSuite(
        search_parser=VivaRealSearchParser(PUBLIC_BASE),
        detail_parser=VivaRealDetailParser(),
        public_base_url=PUBLIC_BASE,
    )
    return VivaRealRentalClient(gateway=VivaRealGateway(transport, builder), parsers=parsers), transport


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    service, transport = _service(client)
    result = service.search_rentals(_criteria(arguments))
    captured = transport.captured()
    raw_search = (captured.json_payload or {}).get("search", {})
    raw_items = raw_search.get("result", {}).get("listings", [])
    native_items = [listing_native(item, raw_items[index]) for index, item in enumerate(result)]
    native = {"listings": native_items}
    if raw_search.get("totalCount") is not None:
        native["total_count"] = raw_search["totalCount"]
    display = [listing_display(item, native_items[index]) for index, item in enumerate(result)]
    return {"native": native, "display": display}


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    public_url = safe_url(arguments["reference"], PROVIDER)
    service, transport = _service(client)
    detail = service.get_property_detail(public_url)
    raw_html = transport.captured().html_document
    native = detail_native(detail, detail_listing(raw_html), product_price(raw_html))
    canonical_url = canonical_detail_url(detail, public_url)
    display = detail_display(detail, native, canonical_url)
    return {"native": native, "display": [display]}


def _facets(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    query = arguments["query"]
    size = arguments.get("size", 10)
    service, _ = _service(client)
    result = service.suggest_locations(query, size=size)
    native = [{
        "label": item.label, "category": item.category.value,
        "location_id": item.location_id.location_id, "city": item.city,
        "state": item.state, "neighborhood": item.neighborhood,
        "coordinate": suggestion_coordinate(item),
    } for item in result]
    display = [{"title": item.label, "location": item.display_full()} for item in result]
    return {"native": native, "display": display}


def _run(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facets(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute search, detail, or location suggestions with safe owned HTTP."""
    validate(operation, arguments)
    if client is not None:
        return json.loads(json.dumps(_run(operation, arguments, client), allow_nan=False))
    with managed_httpx(http2=False, timeout=25.0) as managed_client:
        return json.loads(json.dumps(_run(operation, arguments, managed_client), allow_nan=False))
