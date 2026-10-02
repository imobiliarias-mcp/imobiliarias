"""Bridge adapter for Minas Caixa's existing rental research service."""

import json
from typing import Any
from urllib.parse import urlsplit

import httpx
from minascaixa.application.service import RentalResearchService
from minascaixa.domain.models import (
    FilterBundle,
    LocationScope,
    PaginationSpec,
    PriceBoundary,
    RoomFilter,
    SearchCriteria,
)
from minascaixa.domain.primitives import CitySlug, PageNumber, PropertyCode, RentalPrice, SortOrder
from minascaixa.infrastructure.deserializer import ResponseDeserializer
from minascaixa.infrastructure.http_transport import RequestsHttpTransport

from rental_bridge.errors import BridgeError
from rental_bridge.providers.minascaixaimoveis_validation import validate_arguments
from rental_bridge.transport.safe_http import ensure_response, managed_requests, safe_url

PROVIDER = "minascaixaimoveis"
PUBLIC_BASE_URL = "https://www.minascaixaimoveis.com.br"


class HttpxSessionAdapter:
    """Expose the requests Session calls needed by the source transport over httpx."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client
        self.headers = client.headers

    def post(self, url: str, data: dict[str, Any], timeout: int) -> httpx.Response:
        try:
            response = self._client.post(url, data=data, timeout=timeout, follow_redirects=False)
        except httpx.TransportError as error:
            raise BridgeError("http_error") from error
        return response


class JsonValidatingSession:
    """Guard API responses consistently across managed and injected transports."""

    def __init__(self, session: Any) -> None:
        self._session = session
        self.headers = session.headers

    def post(self, url: str, data: dict[str, Any], timeout: int) -> Any:
        _validate_source_url(url)
        response = self._session.post(url, data=data, timeout=timeout)
        guarded_response = ensure_response(response)
        _validate_json_content(guarded_response.text)
        return guarded_response


def _validate_source_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "www.minascaixaimoveis.com.br":
        raise BridgeError("invalid_input")


def _validate_json_content(content: str) -> None:
    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError) as error:
        raise BridgeError("invalid_content") from error
    if not isinstance(payload, (dict, list)):
        raise BridgeError("invalid_content")


def _criteria(arguments: dict[str, Any]) -> tuple[SearchCriteria, PaginationSpec]:
    city = CitySlug(arguments.get("city", "timoteo"))
    location = LocationScope(city=city, neighborhood_code=0)
    prices = PriceBoundary(
        minimum_price=RentalPrice(float(arguments.get("min_price", 0))),
        maximum_price=RentalPrice(float(arguments.get("max_price", 0))),
    )
    rooms = RoomFilter(arguments.get("bedrooms", 0), arguments.get("parking_spaces", 0))
    criteria = SearchCriteria(location=location, filters=FilterBundle(price_bounds=prices, room_filter=rooms))
    pagination = PaginationSpec(
        page_number=PageNumber(arguments.get("page", 1)),
        sort_order=SortOrder(arguments.get("sort", "valordesc")),
    )
    return criteria, pagination


def _service(session: Any) -> RentalResearchService:
    guarded_session = JsonValidatingSession(session)
    transport = RequestsHttpTransport(guarded_session, timeout_seconds=20)
    deserializer = ResponseDeserializer(public_base_url=PUBLIC_BASE_URL)
    return RentalResearchService(transport, deserializer)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _display_item(item: dict[str, Any]) -> dict[str, Any]:
    neighborhood = item.get("bairro", item.get("neighborhood", ""))
    city = item.get("cidade", item.get("city", ""))
    location = ", ".join(part for part in (str(neighborhood), str(city)) if part)
    code = str(item.get("codigo", item.get("code", "")))
    public_url = item.get("url") or f"{PUBLIC_BASE_URL}/detalhe-imovel/{code}"
    return {
        "reference": code,
        "url": safe_url(public_url, PROVIDER),
        "title": item.get("titulo", item.get("title", "")),
        "location": location,
        "price": item.get("valor", item.get("rental_value")),
    }


def _search(session: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    criteria, pagination = _criteria(arguments)
    total, collection = _service(session).search_rentals(criteria, pagination)
    native_listings = collection.to_dictionary_list()
    native = {"total_count": total, "listings": native_listings}
    display = [_display_summary(item) for item in collection]
    return {"native": _json_safe(native), "display": _json_safe(display)}


def _display_summary(summary: Any) -> dict[str, Any]:
    item = summary.to_dictionary()
    location = summary.core.location
    item["city"] = location.city
    item["neighborhood"] = location.neighborhood
    return _display_item(item)


def _detail(session: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    code = PropertyCode(int(arguments["reference"]))
    native = _service(session).get_property_detail(code)
    display = _display_item(native)
    return {"native": _json_safe(native), "display": [_json_safe(display)]}


def _city_facets(service: RentalResearchService) -> dict[str, Any]:
    cities = service.get_cities()
    return {"cities": [{"city_id": item.code(), "name": item.name()} for item in cities]}


def _neighborhood_facets(service: RentalResearchService, city: str) -> dict[str, Any]:
    neighborhoods = service.get_neighborhoods(CitySlug(city))
    items = [{"neighborhood_id": item.code(), "name": item.name()} for item in neighborhoods]
    return {"neighborhoods": items}


def _facets(session: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    service = _service(session)
    selector = arguments["selector"]
    if selector == "cities":
        native = _city_facets(service)
        return {"native": _json_safe(native), "display": []}
    native = _neighborhood_facets(service, arguments["city"])
    return {"native": _json_safe(native), "display": []}


def _as_guarded_session(client: Any) -> Any:
    if isinstance(client, httpx.Client):
        return HttpxSessionAdapter(client)
    return client


def _execute_with_session(operation: str, arguments: dict[str, Any], session: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(session, arguments)
    if operation == "detail":
        return _detail(session, arguments)
    return _facets(session, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute a rental operation using the guarded requests transport."""
    validate_arguments(operation, arguments)
    if client is not None:
        session = _as_guarded_session(client)
        return _execute_with_session(operation, arguments, session)
    with managed_requests() as session:
        return _execute_with_session(operation, arguments, session)
