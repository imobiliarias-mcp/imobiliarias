"""Bridge adapter for Márcio Imóveis' existing parsed HTML provider."""

import json
from typing import Any

from marcio_research.client.configuration import PortalConfiguration
from marcio_research.client.parsers import FacetParser, PropertyDetailParser, SearchPageParser
from marcio_research.client.query_builder import SearchQueryBuilder
from marcio_research.domain.entities import FacetCatalog, PropertyDetail, SearchPageResult
from marcio_research.domain.value_objects import PropertyCode
from marcio_research.providers.marcio import MarcioRentalProvider

from rental_bridge.errors import BridgeError
from rental_bridge.providers.marcioimoveis_criteria import build_criteria
from rental_bridge.providers.marcioimoveis_transport import VerifiedHttpxTransport
from rental_bridge.transport.safe_http import managed_httpx, safe_url

PROVIDER = "marcioimoveis"


def _provider(client: Any) -> MarcioRentalProvider:
    configuration = PortalConfiguration()
    transport = VerifiedHttpxTransport(client, configuration)
    builder = SearchQueryBuilder(configuration)
    return MarcioRentalProvider(
        configuration=configuration,
        transport=transport,
        query_builder=builder,
        search_parser=SearchPageParser(configuration.base_url),
        detail_parser=PropertyDetailParser(),
        facet_parser=FacetParser(),
    )


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _display_item(item: dict[str, Any]) -> dict[str, Any]:
    location = ", ".join(part for part in (item.get("neighborhood"), item.get("city")) if part)
    property_url = safe_url(item.get("url"), PROVIDER)
    projection = {
        "reference": property_url,
        "url": property_url,
        "title": item.get("title"),
        "location": location,
        "price": item.get("price"),
    }
    return {key: value for key, value in projection.items() if value is not None and value != ""}


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result: SearchPageResult = _provider(client).search_rentals(build_criteria(arguments))
    native = result.to_dictionary()
    display = [_display_item(item) for item in native["listings"]]
    return {"native": _json_safe(native), "display": _json_safe(display)}


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    reference = safe_url(arguments["reference"], PROVIDER)
    detail: PropertyDetail = _provider(client).get_property_detail(PropertyCode(reference))
    native = detail.to_dictionary()
    native["url"] = safe_url(native["url"], PROVIDER)
    return {"native": _json_safe(native), "display": [_json_safe(_display_item(native))]}


def _facet_data(catalog: FacetCatalog) -> dict[str, Any]:
    return catalog.to_dictionary()


def _facets(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    data = _facet_data(_provider(client).get_facets())
    selector = arguments["selector"]
    if selector != "all":
        data = {selector: data[selector]}
    return {"native": _json_safe(data), "display": []}


def _validate(operation: str, arguments: dict[str, Any]) -> None:
    if operation not in {"search", "detail", "facets"} or not isinstance(arguments, dict):
        raise BridgeError("invalid_input")
    allowed = {"locations", "property_types", "bedrooms", "bathrooms", "min_price", "max_price", "sort", "property_id", "keyword", "page"}
    if operation == "detail":
        allowed = {"reference"}
        if not isinstance(arguments.get("reference"), str) or not arguments["reference"].strip():
            raise BridgeError("invalid_input")
    if operation == "facets":
        allowed = {"selector"}
        if arguments.get("selector") not in {"all", "locations", "property_types", "statuses"}:
            raise BridgeError("invalid_input")
    if set(arguments) - allowed:
        raise BridgeError("invalid_input")
    _validate_ranges(arguments)


def _validate_ranges(arguments: dict[str, Any]) -> None:
    lower = arguments.get("min_price")
    upper = arguments.get("max_price")
    if lower is not None and upper is not None and upper > 0 and lower > upper:
        raise BridgeError("invalid_input")


def _execute_with_client(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facets(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute a rental operation with a verified, redirect-free HTTP client."""
    _validate(operation, arguments)
    if client is not None:
        return _execute_with_client(operation, arguments, client)
    with managed_httpx(timeout=20.0) as owned_client:
        return _execute_with_client(operation, arguments, owned_client)
