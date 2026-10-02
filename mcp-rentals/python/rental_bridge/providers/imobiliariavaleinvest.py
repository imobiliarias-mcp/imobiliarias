"""Adapter for Vale Invest rental paths and validated public-card details."""

from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from scripts.client.configuration import ValeInvestConfiguration
from scripts.client.http_transport import ValeInvestHttpTransport
from scripts.client.parsers import (
    ValeInvestFacetParser,
    ValeInvestPropertyDetailParser,
    ValeInvestSearchResultParser,
)
from scripts.client.query_builder import ValeInvestQueryBuilder
from scripts.domain.collections import FacetCollection
from scripts.domain.criteria import RentalFilter
from scripts.domain.value_objects import ListingPrice

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "imobiliariavaleinvest"
_ALLOWED_FILTERS = frozenset({
    "city", "neighborhood", "property_type", "minimum_bedrooms", "minimum_price",
    "maximum_price", "sort_field", "sort_direction", "page", "page_size",
})
_DEFAULT_SORT_FIELD = "valor"
_DEFAULT_SORT_DIRECTION = "crescente"


def _apply_filter(search_filter, arguments):
    if arguments.get("city"):
        search_filter = search_filter.with_city(arguments["city"])
    if arguments.get("neighborhood"):
        search_filter = search_filter.with_neighborhood(arguments["neighborhood"])
    return search_filter


def _apply_specs(search_filter, arguments):
    if arguments.get("property_type"):
        search_filter = search_filter.with_property_type(arguments["property_type"])
    if arguments.get("minimum_bedrooms"):
        search_filter = search_filter.with_bedrooms(arguments["minimum_bedrooms"])
    return search_filter


def _apply_price(search_filter, arguments):
    minimum = arguments.get("minimum_price", 0)
    maximum = arguments.get("maximum_price", 0)
    if minimum > 0 and maximum > 0:
        return search_filter.with_price_range(minimum, maximum)
    if maximum > 0:
        return search_filter.with_price_ceiling(ListingPrice(maximum))
    if minimum > 0:
        return search_filter.with_price_range(minimum, 0)
    return search_filter


def _apply_order_page(search_filter, arguments):
    field = arguments.get("sort_field")
    direction = arguments.get("sort_direction")
    if field or direction:
        search_filter = search_filter.with_sorting(
            field or _DEFAULT_SORT_FIELD, direction or _DEFAULT_SORT_DIRECTION
        )
    if arguments.get("page_size"):
        search_filter = search_filter.with_page_size(arguments["page_size"])
    if arguments.get("page"):
        search_filter = search_filter.with_page(arguments["page"])
    return search_filter


def _search_filter(arguments):
    search_filter = _apply_filter(RentalFilter(), arguments)
    search_filter = _apply_specs(search_filter, arguments)
    search_filter = _apply_price(search_filter, arguments)
    return _apply_order_page(search_filter, arguments)


def _components(client):
    configuration = ValeInvestConfiguration()
    transport = ValeInvestHttpTransport(configuration, http_client=client)
    builder = ValeInvestQueryBuilder(configuration)
    return transport, builder


def _search(arguments):
    search_filter = _search_filter(arguments)
    with managed_httpx() as client:
        transport, builder = _components(client)
        url = builder.build_search_url(search_filter)
        response = ensure_response(transport.get_response(url))
        html = _validate_search_html(response.text)
    parser = ValeInvestSearchResultParser(public_base_url=builder.public_base_url())
    native = parser.parse_search_response(html).to_dictionary()
    display = [_search_display(item) for item in native["listings"]]
    return {"native": native, "display": display}


def _validate_search_html(html):
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one("a.link_resultado") or _has_zero_count_container(soup):
        return html
    raise BridgeError("invalid_content")


def _has_zero_count_container(soup):
    count = soup.find(id="countResultado")
    container = soup.find(id="lista", class_="todos_imoveis")
    return bool(count and count.get("value", "").strip() == "0" and container)


def _search_display(item):
    public_url = safe_url(item["url"], PROVIDER)
    return {"reference": public_url, "url": public_url, "title": item["title"], "location": item["location"], "price": item["rental_price"]}


def _validate_detail_html(url, html):
    target_path = urlsplit(url).path.rstrip("/")
    expected_id = target_path.rsplit("/", 1)[-1]
    soup = BeautifulSoup(html, "html.parser")
    property_id = soup.find(id="pkimovel_ficha")
    canonical = soup.find("link", rel="canonical")
    if not canonical:
        raise BridgeError("invalid_content")
    canonical_path = urlsplit(canonical.get("href", "")).path.rstrip("/")
    if property_id and property_id.get("value") == expected_id and canonical_path == target_path:
        return
    raise BridgeError("invalid_content")


def _detail(arguments):
    target_url = safe_url(arguments["reference"], PROVIDER)
    with managed_httpx() as client:
        transport, builder = _components(client)
        response = ensure_response(transport.get_response(target_url))
        html = response.text
        _validate_detail_html(target_url, html)
    parser = ValeInvestPropertyDetailParser(public_base_url=builder.public_base_url())
    detail = parser.parse_property_detail(html)
    native = detail.to_dictionary()
    native["url"] = safe_url(native["url"], PROVIDER)
    return {"native": native, "display": [_detail_display(native)]}


def _decode_facets(response):
    try:
        data = response.json()
    except ValueError as error:
        raise BridgeError("invalid_content") from error
    catalog = data
    if isinstance(catalog, list) and catalog:
        catalog = catalog[0]
    if not isinstance(catalog, dict) or not isinstance(catalog.get("imoveis"), list):
        raise BridgeError("invalid_content")
    return data


def _detail_display(item):
    return {"reference": item["url"], "url": item["url"], "title": item["title"], "location": item["location"], "price": item["rental_price"]}


def _facets(arguments):
    if arguments != {"selector": "all"}:
        raise BridgeError("invalid_input")
    with managed_httpx() as client:
        transport, builder = _components(client)
        response = ensure_response(transport.get_response(builder.build_facets_url()))
        data = _decode_facets(response)
    result: FacetCollection = ValeInvestFacetParser().parse_facets(data)
    native = result.to_dictionary()
    return {"native": native, "display": []}


def execute(operation: str, arguments: dict) -> dict:
    """Run search, a validated card-URL detail, or an explicitly selected facet."""
    if not isinstance(arguments, dict):
        raise BridgeError("invalid_input")
    if operation == "search" and not set(arguments) - _ALLOWED_FILTERS:
        return _search(arguments)
    if operation == "detail" and set(arguments) == {"reference"}:
        return _detail(arguments)
    if operation == "facets":
        return _facets(arguments)
    raise BridgeError("invalid_input")
