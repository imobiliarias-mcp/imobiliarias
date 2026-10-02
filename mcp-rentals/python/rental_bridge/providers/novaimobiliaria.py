"""Central bridge adapter for Nova Imobiliária's Tecimob API."""

import json
from dataclasses import asdict
from typing import Any
from urllib.parse import urljoin, urlsplit

from nova_research.client import NovaRentalClient
from nova_research.collaborators import RentalNetworkGateway
from nova_research.domain.criteria import SearchCriteria
from nova_research.domain.enums import AreaType, PropertyType, SortOrder
from nova_research.domain.values import AreaRange, PageLimit, PageNumber, PriceRange, RoomCount
from nova_research.infrastructure.http_client import HttpResponse
from nova_research.infrastructure.url_builder import UrlBuilder

from rental_bridge.providers.novaimobiliaria_validation import validate
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "novaimobiliaria"
API_HOST = "api-sites.tecimob.com.br"
PUBLIC_BASE = "https://jnovaimobiliaria.com.br"
TENANT = "jnovaimobiliaria.com.br"


class SafeTransport:
    """Restrict source requests to verified Tecimob API routes and tenant."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, url: str, params: dict[str, str] | None = None) -> HttpResponse:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != API_HOST or not parsed.path.startswith("/api/"):
            raise ValueError("Unexpected Tecimob API target")
        response = ensure_response(self._client.get(
            url, params=params, headers={"x-domain": TENANT, "Accept": "application/json"}
        ))
        if "json" not in response.headers.get("content-type", "").lower():
            raise ValueError("Unexpected non-JSON Tecimob response")
        payload = response.json()
        _validate_api_payload(parsed.path, payload)
        return HttpResponse(response.status_code, response.text, payload, str(response.url))


def _validate_api_payload(path: str, payload: Any) -> None:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), (dict, list)):
        raise TypeError("Unexpected Tecimob API document")
    if path.endswith("/properties") and not isinstance(payload["data"], list):
        raise ValueError("Unexpected Tecimob search response")
    if path.endswith("/filters/states") and not isinstance(payload["data"], list):
        raise ValueError("Unexpected Tecimob states response")
    if path.endswith("/filters/neighborhoods") and not isinstance(payload["data"], list):
        raise ValueError("Unexpected Tecimob neighborhoods response")
    if path.startswith("/api/properties/") and not isinstance(payload["data"], dict):
        raise ValueError("Unexpected Tecimob detail response")


def _room(arguments: dict[str, Any], field: str) -> RoomCount | None:
    count = arguments.get(field)
    if count is None:
        return None
    return RoomCount(count, is_minimum=arguments.get(f"min_{field}", False))


def _area(arguments: dict[str, Any]) -> AreaRange | None:
    area_fields = {"min_area", "max_area", "area_type"}
    if not area_fields.intersection(arguments):
        return None
    return AreaRange(
        arguments.get("min_area"), arguments.get("max_area"),
        AreaType(arguments.get("area_type", "total_area")),
    )


def _criteria(arguments: dict[str, Any]) -> SearchCriteria:
    return SearchCriteria(
        location_slug=arguments.get("city", "timoteo-mg"),
        property_type=PropertyType(arguments.get("property_type", "todos")),
        price=PriceRange(arguments.get("min_price"), arguments.get("max_price")),
        area=_area(arguments), bedrooms=_room(arguments, "bedrooms"),
        suites=_room(arguments, "suites"), garages=_room(arguments, "garages"),
        sort=SortOrder(arguments.get("sort", "-created_at,id")),
        page=PageNumber(arguments.get("offset", 1)), limit=PageLimit(arguments.get("limit", 21)),
    )


def _service(client: Any) -> NovaRentalClient:
    gateway = RentalNetworkGateway(http_client=SafeTransport(client), url_builder=UrlBuilder())
    return NovaRentalClient(gateway=gateway)


def _known_price(amount: Any) -> Any:
    if amount == "Sob Consulta":
        return None
    return amount


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _service(client).search(_criteria(arguments))
    native = result.to_dictionary()
    display = []
    for item in result:
        public_url = safe_url(item.url, PROVIDER)
        address = item.address_formatted
        display.append({
            "reference": item.identity.reference or item.identity.property_id,
            "url": public_url,
            "title": item.title,
            "location": address or None,
            "price": _known_price(item.pricing.amount),
        })
    return {"native": native, "display": display}


def _detail_display(detail: Any, public_url: str | None) -> dict[str, Any]:
    return {
        "reference": detail.identity.reference or detail.identity.property_id,
        "url": public_url,
        "title": detail.title,
        "location": detail.location.formatted or None,
        "price": _known_price(detail.pricing.amount),
    }


def _public_url(canonical_path: str | None) -> str | None:
    if not canonical_path:
        return None
    target = urljoin(PUBLIC_BASE + "/", canonical_path)
    return safe_url(target, PROVIDER)


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    detail = _service(client).get_details(arguments["reference"])
    public_url = _public_url(detail.canonical_path)
    return {"native": asdict(detail), "display": [_detail_display(detail, public_url)]}


def _catalog_data(catalog: Any) -> dict[str, Any]:
    return asdict(catalog)


def _facets(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    native = _catalog_data(_service(client).get_locations())
    return {"native": native, "display": []}



def _run(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facets(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute search, detail, or location facets with the source client."""
    validate(operation, arguments)
    if client is not None:
        return json.loads(json.dumps(_run(operation, arguments, client), allow_nan=False))
    with managed_httpx(timeout=15.0) as managed_client:
        return json.loads(json.dumps(_run(operation, arguments, managed_client), allow_nan=False))
