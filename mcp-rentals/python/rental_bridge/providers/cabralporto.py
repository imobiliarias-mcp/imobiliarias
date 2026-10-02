"""Safe bridge adapter for Cabral Porto's core rental client."""

import json
from typing import Any

from cabralporto_research.client import CabralPortoRentalClient
from cabralporto_research.collaborators import RentalNetworkGateway
from cabralporto_research.domain.criteria import (
    SearchCriteria,
    SearchFilterBundle,
    SearchPaginationBundle,
)
from cabralporto_research.domain.enums import PropertyType, SortOrder, TransactionType
from cabralporto_research.domain.values import AreaRange, PageNumber, PriceRange, RoomCount
from cabralporto_research.infrastructure.url_builder import UrlBuilder

from rental_bridge.providers.cabralporto_http import SafeTransport
from rental_bridge.providers.cabralporto_projection import known_fields
from rental_bridge.providers.cabralporto_validation import validate
from rental_bridge.transport.safe_http import managed_httpx, safe_url

PROVIDER = "cabralporto"


def _room_count(arguments: dict[str, Any], name: str, minimum: bool = True) -> RoomCount | None:
    if name not in arguments:
        return None
    return RoomCount(arguments[name], is_minimum=minimum)


def _criteria(arguments: dict[str, Any]) -> SearchCriteria:
    filters = _filter_bundle(arguments)
    pagination = _pagination_bundle(arguments)
    return SearchCriteria(filters=filters, pagination=pagination)


def _filter_bundle(arguments: dict[str, Any]) -> SearchFilterBundle:
    return SearchFilterBundle(
        transaction=TransactionType.ALUGAR,
        property_type=PropertyType(arguments.get("property_type", "imoveis")),
        city_slug=arguments.get("city_slug", "timoteo-mg"),
        neighborhood_slug=arguments.get("neighborhood_slug"),
        price=PriceRange(arguments.get("min_price"), arguments.get("max_price")),
        area=AreaRange(arguments.get("min_area"), arguments.get("max_area"), arguments.get("area_type", "total_area")),
        bedrooms=_room_count(arguments, "bedrooms", arguments.get("min_bedrooms", True)),
        suites=_room_count(arguments, "suites"),
        garages=_room_count(arguments, "garages"),
    )


def _pagination_bundle(arguments: dict[str, Any]) -> SearchPaginationBundle:
    page = PageNumber(arguments.get("page", 1), arguments.get("limit", 21))
    sort = SortOrder(arguments.get("sort", "-created_at,id"))
    return SearchPaginationBundle(page=page, sort=sort)


def _service(client: Any) -> CabralPortoRentalClient:
    builder = UrlBuilder()
    gateway = RentalNetworkGateway(http_client=SafeTransport(client), url_builder=builder)
    return CabralPortoRentalClient(gateway=gateway)


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    collection = _service(client).search(_criteria(arguments))
    listings = [_safe_listing(item) for item in collection.to_list()]
    native = {"listings": listings, "total_count": collection.total_count, "current_page": collection.current_page, "total_pages": collection.total_pages}
    display = [_display_item(item) for item in listings]
    return {"native": _json_safe(native), "display": _json_safe(display)}


def _safe_listing(item: dict[str, Any]) -> dict[str, Any]:
    item["url"] = safe_url(item.get("url") or item.get("detail_url"), PROVIDER)
    return item


def _display_item(item: dict[str, Any]) -> dict[str, Any]:
    values = {
        "reference": item.get("reference"),
        "url": item.get("url") or item.get("detail_url"),
        "title": item.get("title"),
        "location": item.get("formatted_address"),
        "price": item.get("price"),
    }
    return known_fields(values)


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _service(client).get_details(arguments["reference"])
    native = result.to_dictionary()
    native["canonical_url"] = safe_url(native["canonical_url"], PROVIDER)
    display = known_fields(
        {
            "reference": native.get("reference"),
            "url": native.get("canonical_url"),
            "title": native.get("title"),
            "location": native.get("formatted_address"),
            "price": native.get("price"),
        }
    )
    return {"native": _json_safe(native), "display": [_json_safe(display)]}


def _facet_data(result: Any, selector: str) -> dict[str, Any]:
    facets = result.to_dictionary()
    if selector == "all":
        return facets
    return {selector: facets[selector]}


def _facet_result(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _service(client).get_facets()
    facets = _facet_data(result, arguments.get("selector", "all"))
    return {"native": _json_safe(facets), "display": []}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _run(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facet_result(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute one operation with an injected client or owned safe client."""
    validate(operation, arguments)
    if client is not None:
        return _run(operation, arguments, client)
    with managed_httpx(verify=True, follow_redirects=False, timeout=15.0) as owned_client:
        return _run(operation, arguments, owned_client)
