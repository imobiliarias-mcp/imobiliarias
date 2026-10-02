"""Safe bridge adapter for Casa Linhares' existing Imobzi provider."""

import json
from typing import Any

from scripts.client.configuration import ImobziConfiguration
from scripts.client.http_transport import ImobziHttpTransport
from scripts.client.resolver import TenantDatabaseResolver
from scripts.domain.criteria import (
    LocationCriteria,
    PriceRange,
    RentalFilter,
    RentalSearchCriteria,
    SearchConstraints,
    SearchPagination,
    SpecificationCriteria,
)
from scripts.domain.value_objects import ListingPrice, PropertyCode
from scripts.providers.casalinhares import CasaLinharesRentalProvider

from rental_bridge.errors import BridgeError
from rental_bridge.providers.casalinhares_validation import validate
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "casalinhares"


class SafeClient:
    """Guard each Imobzi request while preserving its response interface."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
        response = ensure_response(self._client.get(url, params=params, headers=headers))
        if "json" not in response.headers.get("content-type", "").lower():
            raise BridgeError("invalid_content")
        return response


def _filter(arguments: dict[str, Any]) -> RentalFilter:
    location = LocationCriteria(city=arguments.get("city", ""), neighborhood=arguments.get("neighborhood", ""))
    specifications = SpecificationCriteria(property_type=arguments.get("property_type", ""), minimum_bedrooms=arguments.get("bedrooms", 0))
    criteria = RentalSearchCriteria(location=location, specifications=specifications)
    constraints = _constraints(arguments)
    return RentalFilter(criteria=criteria, constraints=constraints)


def _constraints(arguments: dict[str, Any]) -> SearchConstraints:
    minimum = ListingPrice(float(arguments.get("min_price", 0)))
    maximum = ListingPrice(float(arguments.get("max_price", 0)))
    price_range = PriceRange(minimum_price=minimum, maximum_price=maximum)
    pagination = SearchPagination(page_number=arguments.get("page", 1), cursor_token=arguments.get("cursor", ""))
    return SearchConstraints(price_range=price_range, pagination=pagination)


def _provider(client: Any) -> CasaLinharesRentalProvider:
    configuration = ImobziConfiguration()
    transport = ImobziHttpTransport(configuration=configuration, http_client=SafeClient(client))
    resolver = TenantDatabaseResolver(transport=transport, configuration=configuration)
    return CasaLinharesRentalProvider(transport=transport, resolver=resolver)


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _provider(client).search_rentals(_filter(arguments))
    native = result.to_dictionary()
    display = [_display_item(item) for item in native["listings"]]
    return {"native": _json_safe(native), "display": _json_safe(display)}


def _display_item(item: dict[str, Any]) -> dict[str, Any]:
    values = {
        "reference": item.get("code"),
        "url": safe_url(item.get("url"), PROVIDER),
        "title": item.get("title"),
        "location": item.get("location"),
        "price": item.get("rental_price"),
    }
    return _known_fields(values)


def _known_fields(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None and value != ""}


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    code = PropertyCode(arguments["reference"])
    result = _provider(client).get_property_detail(code)
    native = result.to_dictionary()
    native["url"] = safe_url(native.get("url"), PROVIDER)
    return {"native": _json_safe(native), "display": [_json_safe(_display_item(native))]}


def _selected_facets(result: dict[str, Any], selector: str) -> dict[str, Any]:
    if selector == "all":
        return result
    return {selector: result[selector]}


def _facet_result(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    result = _provider(client).get_facets().to_dictionary()
    facets = _selected_facets(result, arguments.get("selector", "all"))
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
    """Execute one operation with injected or bridge-owned safe HTTP transport."""
    validate(operation, arguments)
    if client is not None:
        return _run(operation, arguments, client)
    with managed_httpx(verify=True, follow_redirects=False, timeout=15.0) as owned_client:
        return _run(operation, arguments, owned_client)
