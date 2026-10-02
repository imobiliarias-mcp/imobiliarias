"""Adapter for Portal Imóveis MG using its Orangeimob builder and parsers."""
import re
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from scripts.client.configuration import PortalMGConfiguration
from scripts.client.http_transport import PortalMGHttpTransport
from scripts.client.query_builder import RentalQueryBuilder
from scripts.domain.collections import FacetCollection
from scripts.domain.criteria import (
    ConstraintCriteria,
    LocationFilter,
    PageOffset,
    PriceRange,
    PropertyFilter,
    RentalFilter,
    ScopeCriteria,
)
from scripts.domain.value_objects import PropertyCode
from scripts.providers.portalmg import PortalMGRentalProvider

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "imobiliariaportalmg"
_ALLOWED_FILTERS = frozenset({
    "city_id", "neighborhood", "category_id", "subcategory_id", "bedrooms", "suites",
    "garages", "reference", "minimum_price", "maximum_price", "page", "page_size",
    "sort_order",
})


class _GuardedTransport:
    """Guard responses before allowing source parsers to see portal text."""

    def __init__(self, transport):
        self._transport = transport

    def get_text(self, url, params=None):
        response = ensure_response(self._transport.get_response(url, params))
        _validate_listing_html(url, response.text)
        _validate_detail_html(url, response.text)
        return response.text

    def post_form(self, url, data):
        return self._transport.post_form(url, data)


def _validate_listing_html(url, html):
    if not urlsplit(url).path.endswith("imoveis_listagem.php"):
        return
    soup = BeautifulSoup(html, "html.parser")
    is_facet_form = not urlsplit(url).query and soup.select_one("#sl-cidade")
    if soup.select_one(".li-imovel") or _has_empty_results_marker(soup) or is_facet_form:
        return
    raise BridgeError("invalid_content")


def _has_empty_results_marker(soup):
    page_text = soup.get_text(" ", strip=True).lower()
    return "nenhum im" in page_text or "não foram encontrados" in page_text


def _validate_detail_html(url, html):
    parts = urlsplit(url)
    if not parts.path.endswith("imoveis_detalhes.php"):
        return
    identifiers = parse_qs(parts.query).get("id", [])
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".imovel__titulo")
    if len(identifiers) == 1 and _title_contains_identifier(title, identifiers[0]):
        return
    raise BridgeError("invalid_content")


def _title_contains_identifier(title, identifier):
    if not title or not identifier:
        return False
    pattern = rf"(?<![0-9]){re.escape(identifier)}(?![0-9])"
    return bool(re.search(pattern, title.get_text(" ", strip=True)))


def _price_range(arguments):
    minimum = float(arguments.get("minimum_price", 0))
    maximum = float(arguments.get("maximum_price", 0))
    return PriceRange(minimum=minimum, maximum=maximum)


def _page_offset(arguments):
    return PageOffset(page=arguments.get("page", 1), page_size=arguments.get("page_size", 10))


def _property_filter(arguments):
    return PropertyFilter(
        category_id=arguments.get("category_id", ""),
        subcategory_id=arguments.get("subcategory_id", ""),
        bedrooms=arguments.get("bedrooms", 0), suites=arguments.get("suites", 0),
        garages=arguments.get("garages", 0), reference=arguments.get("reference", ""),
    )


def _rental_filter(arguments):
    location = LocationFilter(arguments.get("city_id", ""), arguments.get("neighborhood", ""))
    scope = ScopeCriteria(location=location, properties=_property_filter(arguments))
    constraints = ConstraintCriteria(
        price_range=_price_range(arguments), pagination=_page_offset(arguments),
        transaction="locacao", sort_order=arguments.get("sort_order", "menor_valor"),
    )
    return RentalFilter(scope=scope, constraints=constraints)


def _provider(client):
    config = PortalMGConfiguration()
    source_transport = PortalMGHttpTransport(config, http_client=client)
    return PortalMGRentalProvider(_GuardedTransport(source_transport), RentalQueryBuilder(config))


def _display_listing(item):
    return {"reference": item["property_id"], "url": safe_url(item["url"], PROVIDER), "title": item["category"], "location": f'{item["neighborhood"]}, {item["city"]}'.strip(", "), "price": item["rental_price"]}


def _search(arguments):
    with managed_httpx() as client:
        result = _provider(client).search_rentals(_rental_filter(arguments))
    native = result.to_dictionary()
    display = [_display_listing(item) for item in native["listings"]]
    return {"native": native, "display": display}


def _detail(arguments):
    reference = arguments["reference"]
    if not re.fullmatch(r"[0-9]{1,20}", reference):
        raise BridgeError("invalid_input")
    with managed_httpx() as client:
        detail = _provider(client).get_property_detail(PropertyCode(reference))
    native = detail.to_dictionary()
    native["url"] = safe_url(native["url"], PROVIDER)
    display = [{"reference": native["reference"], "url": native["url"], "title": native["category"], "location": f'{native["neighborhood"]}, {native["city"]}'.strip(", "), "price": native["rental_price"]}]
    return {"native": native, "display": display}


def _facets(arguments):
    if arguments != {"selector": "all"}:
        raise BridgeError("invalid_input")
    with managed_httpx() as client:
        result: FacetCollection = _provider(client).get_facets()
    return {"native": result.to_dictionary(), "display": []}


def execute(operation: str, arguments: dict) -> dict:
    """Run search, detail, or facets with verified, non-redirecting transport."""
    if not isinstance(arguments, dict):
        raise BridgeError("invalid_input")
    if operation == "search" and not set(arguments) - _ALLOWED_FILTERS:
        return _search(arguments)
    if operation == "detail" and set(arguments) == {"reference"}:
        return _detail(arguments)
    if operation == "facets":
        return _facets(arguments)
    raise BridgeError("invalid_input")
