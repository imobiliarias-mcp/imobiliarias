"""Safe bridge adapter for Alê Corretora MG's existing rental client."""

import json
from typing import Any

from alecorretora_research.client import AleCorretoraRentalClient
from alecorretora_research.collaborators import RentalNetworkGateway
from alecorretora_research.domain.enums import PropertyType
from alecorretora_research.infrastructure.http_client import HttpResponse
from alecorretora_research.infrastructure.payload_builder import RequestPayloadBuilder

from rental_bridge.errors import BridgeError
from rental_bridge.providers.alecorretoramg_validation import validate
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "alecorretoramg"


class SafeTransport:
    """Adapt an owned bridge client to the agency's HTTP protocol."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        response = ensure_response(self._client.get(url, headers=headers))
        self._validate_get_content(response, url)
        return _response(response)

    def post(self, url: str, data: Any, headers: dict[str, str] | None = None) -> HttpResponse:
        response = ensure_response(self._client.post(url, data=data, headers=headers))
        self._validate_search_content(response)
        return _response(response)

    def _validate_get_content(self, response: Any, url: str) -> None:
        if "/wp-json/" in url:
            _require_json(response)
            return
        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type or "<h1" not in response.text.lower():
            raise BridgeError("invalid_content")

    def _validate_search_content(self, response: Any) -> None:
        result = _response(response)
        payload = result.json_data
        if isinstance(payload, dict) and isinstance(payload.get("content"), str):
            return
        body = response.text.lower()
        if "jet-listing-grid" in body:
            return
        raise BridgeError("invalid_content")


def _require_json(response: Any) -> None:
    if "json" not in response.headers.get("content-type", "").lower():
        raise BridgeError("invalid_content")
    try:
        payload = response.json()
    except ValueError as error:
        raise BridgeError("invalid_content") from error
    if not isinstance(payload, (dict, list)):
        raise BridgeError("invalid_content")


def _response(response: Any) -> HttpResponse:
    try:
        json_data = response.json()
    except ValueError:
        json_data = None
    return HttpResponse(response.status_code, response.text, str(response.url), json_data)


def _serialize_detail(detail: Any) -> dict[str, Any]:
    public_url = safe_url(detail.url, PROVIDER)
    return {
        "property_id": detail.property_id,
        "url": public_url,
        "code": detail.code,
        "title": detail.title,
        "purpose": detail.purpose,
        "price_formatted": detail.price_formatted,
        "description": detail.description,
        "location": {"neighborhood": detail.location.neighborhood, "city": detail.location.city, "state": detail.location.state},
        "specs": {"bedrooms": detail.specs.bedrooms, "bathrooms": detail.specs.bathrooms, "parking_spaces": detail.specs.parking_spaces, "area": detail.specs.area},
        "gallery": list(detail.gallery),
    }


def _location_label(item: dict[str, Any]) -> str:
    location = item.get("location")
    if isinstance(location, dict):
        return ", ".join(value for value in (location.get("neighborhood", ""), location.get("city", "")) if value)
    return ", ".join(value for value in (item.get("neighborhood", ""), item.get("city", "")) if value)


def _safe_listing(item: dict[str, Any]) -> dict[str, Any]:
    item["url"] = safe_url(item["url"], PROVIDER)
    return item


def _display_item(item: dict[str, Any]) -> dict[str, Any]:
    values = {
        "reference": item.get("code") or item.get("property_id"),
        "url": item.get("url"),
        "title": item.get("title"),
        "location": _location_label(item),
        "price": item.get("price_formatted"),
    }
    return _known_fields(values)


def _known_fields(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None and value != ""}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _facets(catalog: Any, selector: str) -> dict[str, Any]:
    facets = {
        "cities": [{"city_id": item.city_id, "name": item.name, "slug": item.slug} for item in catalog.cities],
        "neighborhoods": [{"neighborhood_id": item.neighborhood_id, "name": item.name, "slug": item.slug, "city_id": item.city_id} for item in catalog.neighborhoods],
    }
    if selector == "all":
        return facets
    return {selector: facets[selector]}


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    gateway = RentalNetworkGateway(http_client=SafeTransport(client), payload_builder=RequestPayloadBuilder())
    rental_client = AleCorretoraRentalClient(gateway=gateway)
    result = rental_client.search_rentals(
        city_id=arguments.get("city_id"), neighborhood_id=arguments.get("neighborhood_id"),
        property_type=PropertyType(arguments.get("property_type", "")), bedrooms=arguments.get("bedrooms"),
        bathrooms=arguments.get("bathrooms"), min_price=arguments.get("min_price"),
        max_price=arguments.get("max_price"), code=arguments.get("code"), page=arguments.get("page", 1),
    )
    native = result.to_dictionary()
    native["listings"] = [_safe_listing(item) for item in native["listings"]]
    display = [_display_item(item) for item in native["listings"]]
    return {"native": _json_safe(native), "display": _json_safe(display)}


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    gateway = RentalNetworkGateway(http_client=SafeTransport(client), payload_builder=RequestPayloadBuilder())
    result = AleCorretoraRentalClient(gateway=gateway).get_details(arguments["reference"])
    native = _serialize_detail(result)
    return {"native": _json_safe(native), "display": [_display_item(native)]}


def _facet_result(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    gateway = RentalNetworkGateway(http_client=SafeTransport(client), payload_builder=RequestPayloadBuilder())
    result = AleCorretoraRentalClient(gateway=gateway).get_locations()
    return {"native": _json_safe(_facets(result, arguments.get("selector", "all"))), "display": []}


def _run(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facet_result(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute one source operation using an injected or managed safe HTTP client."""
    validate(operation, arguments)
    if client is not None:
        return _run(operation, arguments, client)
    with managed_httpx(verify=True, follow_redirects=False, timeout=20.0) as owned_client:
        return _run(operation, arguments, owned_client)
