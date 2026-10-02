"""Safe bridge adapter for Arthuso Imóveis' existing research service."""

import json
from typing import Any

from arthuso import (
    BathroomCount,
    BedroomCount,
    CitySlug,
    NeighborhoodSlug,
    PageNumber,
    PaginationSpec,
    PropertyCode,
    PropertyId,
    PropertyTypeSlug,
    RentalPrice,
    RentalResearchService,
    ResponseDeserializer,
    SearchCriteria,
    SortOrder,
)
from arthuso.infrastructure.endpoints import BASE_URL

from rental_bridge.providers.arthusoimoveis_http import SafeTransport
from rental_bridge.providers.arthusoimoveis_validation import validate
from rental_bridge.transport.safe_http import managed_httpx, safe_url

PROVIDER = "arthusoimoveis"


def _criteria(arguments: dict[str, Any]) -> SearchCriteria:
    values = {
        "city": _optional_value(CitySlug, arguments.get("city")),
        "neighborhood": _optional_value(NeighborhoodSlug, arguments.get("neighborhood")),
        "property_type": _optional_value(PropertyTypeSlug, arguments.get("property_type")),
        "bedrooms": _optional_argument(arguments, "bedrooms", BedroomCount),
        "bathrooms": _optional_argument(arguments, "bathrooms", BathroomCount),
        "min_price": _optional_argument(arguments, "min_price", RentalPrice),
        "max_price": _optional_argument(arguments, "max_price", RentalPrice),
        "property_code": _optional_value(PropertyCode, arguments.get("property_code")),
        "keyword": arguments.get("keyword"),
        "sort_by": _optional_value(SortOrder, arguments.get("sort_by")),
    }
    return SearchCriteria(**values)


def _optional_value(value_type: Any, value: Any) -> Any:
    if not value:
        return None
    return value_type(value)


def _optional_argument(arguments: dict[str, Any], name: str, value_type: Any) -> Any:
    if name not in arguments:
        return None
    return value_type(arguments[name])


def _serialize_detail(detail: Any) -> dict[str, Any]:
    return {
        "summary": detail.summary.to_dictionary(),
        "description": detail.description,
        "meta": detail.meta,
        "terms": detail.terms,
    }


def _public_listing_url(item: dict[str, Any]) -> str:
    raw_url = item.get("url") or item.get("detail_url")
    return safe_url(raw_url, PROVIDER)


def _safe_item_url(item: dict[str, Any]) -> dict[str, Any]:
    item["url"] = _public_listing_url(item)
    return item


def _display_item(item: dict[str, Any]) -> dict[str, Any]:
    return _known_fields(
        {
            "reference": _typed_reference(item),
            "url": _optional_public_url(item),
            "title": item.get("title"),
            "price": item.get("price_text"),
        }
    )


def _typed_reference(item: dict[str, Any]) -> dict[str, str] | None:
    post_id = item.get("post_id")
    if post_id is not None and str(post_id).strip():
        return {"kind": "id", "value": str(post_id)}
    slug = item.get("slug")
    if isinstance(slug, str) and slug.strip():
        return {"kind": "slug", "value": slug}
    return None


def _optional_public_url(item: dict[str, Any]) -> str | None:
    raw_url = item.get("url") or item.get("detail_url")
    if not raw_url:
        return None
    return safe_url(raw_url, PROVIDER)


def _known_fields(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value is not None and value != ""}


def _facet_items(collection: Any) -> list[dict[str, Any]]:
    return [{"term_id": item.term_id, "name": item.name, "slug": item.slug, "count": item.count} for item in collection]


def _facet_data(service: RentalResearchService, selector: str) -> dict[str, Any]:
    if selector == "cities":
        return {"cities": _facet_items(service.get_cities())}
    if selector == "neighborhoods":
        return {"neighborhoods": _facet_items(service.get_neighborhoods())}
    if selector == "property_types":
        return {"property_types": _facet_items(service.get_property_types())}
    return {
        "cities": _facet_items(service.get_cities()),
        "neighborhoods": _facet_items(service.get_neighborhoods()),
        "property_types": _facet_items(service.get_property_types()),
    }


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    criteria = _criteria(arguments)
    pagination = PaginationSpec(page=PageNumber(arguments.get("page", 1)))
    service = _service(client)
    result = service.search_rentals(criteria, pagination)
    native = result.to_dictionary()
    native["items"] = [_safe_item_url(item) for item in native["items"]]
    display = [_display_item(item) for item in native["items"]]
    return {"native": _json_safe(native), "display": _json_safe(display)}


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    service = _service(client)
    reference = arguments["reference"]
    result = _lookup_property(service, reference)
    native = _serialize_detail(result)
    native["summary"] = _safe_item_url(native["summary"])
    display = _detail_display(reference, native["summary"])
    return {"native": _json_safe(native), "display": [_json_safe(display)]}


def _lookup_property(service: RentalResearchService, reference: dict[str, str]) -> Any:
    if reference["kind"] == "id":
        return service.get_property_by_id(PropertyId(int(reference["value"])))
    return service.get_property_by_slug(reference["value"])


def _detail_display(reference: dict[str, str], item: dict[str, Any]) -> dict[str, Any]:
    return _known_fields(
        {
            "reference": reference,
            "url": item.get("url"),
            "title": item.get("title"),
            "price": item.get("price_text"),
        }
    )


def _facet_result(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    service = _service(client)
    facets = _facet_data(service, arguments.get("selector", "all"))
    return {"native": _json_safe(facets), "display": []}


def _service(client: Any) -> RentalResearchService:
    return RentalResearchService(SafeTransport(client), ResponseDeserializer(), public_base_url=BASE_URL)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _run(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facet_result(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute one operation using an injected or bridge-owned TLS client."""
    validate(operation, arguments)
    if client is not None:
        return _run(operation, arguments, client)
    with managed_httpx(verify=True, follow_redirects=False, timeout=20.0) as owned_client:
        return _run(operation, arguments, owned_client)
