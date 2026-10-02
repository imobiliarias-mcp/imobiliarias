"""Adapter for the Epifanio Imóveis rental research client."""
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from epifanio_research.client import EpifanioRentalClient
from epifanio_research.collaborators import RentalNetworkGateway
from epifanio_research.domain.criteria import (
    FacilityCriteria,
    FeatureBundle,
    FilterBundle,
    LocationCriteria,
    RoomCriteria,
    SearchCriteria,
    SearchScope,
)
from epifanio_research.domain.enums import PropertyType, SortOrder, TransactionType
from epifanio_research.domain.values import AreaRange, PageNumber, PriceRange, RoomCount
from epifanio_research.infrastructure.http_client import HttpResponse
from epifanio_research.infrastructure.url_builder import UrlBuilder

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "epifanioimoveis"
_ALLOWED_FILTERS = frozenset({
    "city", "property_type", "minimum_price", "maximum_price", "minimum_area",
    "maximum_area", "bedrooms", "minimum_bedrooms", "suites", "minimum_suites",
    "bathrooms", "minimum_bathrooms", "parking_spaces", "minimum_parking_spaces",
    "neighborhood_ids", "sort_order", "reference_code", "page",
})


class _GuardedHttpClient:
    """Adapt the owned guarded client to Epifanio's public HTTP interface."""

    def __init__(self, client, allow_location_catalog=False):
        self._client = client
        self._allow_location_catalog = allow_location_catalog

    def get(self, url):
        response = ensure_response(self._client.get(url))
        _validate_search_html(url, response.text, self._allow_location_catalog)
        _validate_detail_html(url, response.text)
        return HttpResponse(response.status_code, response.text, str(response.url))


def _validate_search_html(url, html, allow_location_catalog):
    if not urlsplit(url).path.startswith("/imovel/locacao/"):
        return
    soup = BeautifulSoup(html, "html.parser")
    is_catalog = allow_location_catalog and "dgCidadesBairros" in html
    if soup.select_one(".imovelcard") or _has_empty_results_marker(soup) or is_catalog:
        return
    raise BridgeError("invalid_content")


def _has_empty_results_marker(soup):
    page_text = soup.get_text(" ", strip=True).lower()
    return "nenhum im" in page_text or "não foram encontrados" in page_text


def _validate_detail_html(url, html):
    target_path = urlsplit(url).path.rstrip("/")
    match = re.fullmatch(r"/imovel/([0-9]+)", target_path)
    if not match:
        return
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".imovel__titulo")
    canonical = soup.find("link", rel="canonical")
    if not canonical:
        raise BridgeError("invalid_content")
    canonical_path = urlsplit(canonical.get("href", "")).path.rstrip("/")
    if title and title.get_text(strip=True) and canonical_path == target_path:
        return
    raise BridgeError("invalid_content")


def _room(arguments, key, minimum_key):
    count = arguments.get(key)
    if count is None:
        return None
    return RoomCount(count, arguments.get(minimum_key, False))


def _criteria(arguments):
    rooms = RoomCriteria(_room(arguments, "bedrooms", "minimum_bedrooms"), _room(arguments, "suites", "minimum_suites"))
    facilities = FacilityCriteria(_room(arguments, "bathrooms", "minimum_bathrooms"), _room(arguments, "parking_spaces", "minimum_parking_spaces"))
    return SearchCriteria(
        scope=SearchScope(TransactionType.LOCACAO, PropertyType(arguments.get("property_type", "todos"))),
        location=LocationCriteria(arguments.get("city", "timoteo"), tuple(arguments.get("neighborhood_ids", []))),
        filters=FilterBundle(PriceRange(arguments.get("minimum_price"), arguments.get("maximum_price")), AreaRange(arguments.get("minimum_area"), arguments.get("maximum_area"))),
        features=FeatureBundle(rooms, facilities),
        sort_order=SortOrder(arguments.get("sort_order", "")),
        page=PageNumber(arguments.get("page", 1)),
        reference_code=arguments.get("reference_code"),
    )


def _client(http_client, allow_location_catalog=False):
    guarded_client = _GuardedHttpClient(http_client, allow_location_catalog)
    gateway = RentalNetworkGateway(guarded_client, UrlBuilder())
    return EpifanioRentalClient(gateway=gateway)


def _safe_listing_urls(native):
    for item in native["items"]:
        item["url"] = safe_url(item["url"], PROVIDER)
    return native


def _location_text(location):
    values = [location["neighborhood"], location["city"]]
    return ", ".join(value for value in values if value)


def _listing_display(item):
    return {"reference": item["property_id"], "url": item["url"], "title": item["title"], "location": _location_text(item["location"]), "price": item["price_text"]}


def _search(arguments):
    criteria = _criteria(arguments)
    with managed_httpx() as http_client:
        result = _client(http_client).search(criteria)
    native = _safe_listing_urls(result.to_dictionary())
    return {"native": native, "display": [_listing_display(item) for item in native["items"]]}


def _overview(detail):
    value = detail.overview
    return {"property_id": value.property_id, "title": value.title, "reference_code": value.reference_code, "description": value.description}


def _pricing(detail):
    value = detail.pricing
    return {"amount": value.amount, "currency": value.currency, "formatted_text": value.formatted_text}


def _property_location(detail):
    value = detail.location
    return {"address": value.address, "neighborhood": value.neighborhood, "city": value.city, "state": value.state}


def _specifications(detail):
    value = detail.specs
    return {"bedrooms": value.bedrooms, "suites": value.suites, "bathrooms": value.bathrooms, "parking_spaces": value.parking_spaces}


def _detail_native(detail):
    return {"overview": _overview(detail), "pricing": _pricing(detail), "location": _property_location(detail), "specs": _specifications(detail), "characteristics": list(detail.characteristics), "photos": list(detail.photos), "canonical_url": safe_url(detail.canonical_url, PROVIDER)}


def _detail_display(native):
    overview = native["overview"]
    location = native["location"]
    return [{"reference": overview["property_id"], "url": native["canonical_url"], "title": overview["title"], "location": _location_text(location), "price": native["pricing"]["amount"]}]


def _detail(arguments):
    reference = arguments["reference"]
    if not re.fullmatch(r"[0-9]{1,20}", reference):
        raise BridgeError("invalid_input")
    with managed_httpx() as http_client:
        result = _client(http_client).get_details(reference)
    native = _detail_native(result)
    return {"native": native, "display": _detail_display(native)}


def _catalog_native(catalog):
    return {"cities": [_city(city) for city in catalog.cities]}


def _city(city):
    return {"name": city.name, "slug": city.slug, "neighborhoods": [_neighborhood(item) for item in city.neighborhoods]}


def _neighborhood(neighborhood):
    return {"name": neighborhood.name, "slug": neighborhood.slug, "numeric_id": neighborhood.numeric_id}


def _facets(arguments):
    if arguments != {"selector": "locations"}:
        raise BridgeError("invalid_input")
    with managed_httpx() as http_client:
        catalog = _client(http_client, allow_location_catalog=True).get_locations()
    return {"native": _catalog_native(catalog), "display": []}


def execute(operation: str, arguments: dict) -> dict:
    """Run one rental search, property detail, or location-facet operation."""
    if not isinstance(arguments, dict):
        raise BridgeError("invalid_input")
    if operation == "search" and not set(arguments) - _ALLOWED_FILTERS:
        return _search(arguments)
    if operation == "detail" and set(arguments) == {"reference"}:
        return _detail(arguments)
    if operation == "facets":
        return _facets(arguments)
    raise BridgeError("invalid_input")
