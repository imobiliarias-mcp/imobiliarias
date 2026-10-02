"""Adapter for Helena Imóveis rental searches and public property details."""
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
from helena_research.application.service import HelenaResearchService, TransportCoordinator
from helena_research.domain.criteria import (
    FacilityCriteria,
    FeatureBundle,
    FilterBundle,
    LocationCriteria,
    RoomCriteria,
    SearchCriteria,
    SearchScope,
)
from helena_research.domain.enums import PropertyType, SortOrder, TransactionType
from helena_research.domain.values import AreaRange, PageNumber, PriceRange, RoomCount
from helena_research.infrastructure.http_client import HttpResponse
from helena_research.infrastructure.url_builder import UrlBuilder

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "helenaimoveis"
_ALLOWED_FILTERS = frozenset({
    "city", "neighborhood", "property_type", "minimum_price", "maximum_price",
    "minimum_area", "maximum_area", "bedrooms", "minimum_bedrooms", "suites",
    "minimum_suites", "bathrooms", "minimum_bathrooms", "parking_spaces",
    "minimum_parking_spaces", "neighborhood_ids", "sort_order", "reference_code", "page",
})


class _GuardedHttpClient:
    """Expose Helena's response interface over the owned guarded HTTP client."""

    def __init__(self, client):
        self._client = client

    def get(self, url):
        response = ensure_response(self._client.get(url))
        _validate_search_html(url, response.text)
        _validate_detail_html(url, response.text)
        return HttpResponse(response.status_code, response.text, str(response.url))


def _validate_search_html(url, html):
    if not urlsplit(url).path.startswith("/imovel/locacao/"):
        return
    soup = BeautifulSoup(html, "html.parser")
    if soup.select_one(".imovelcard") or _has_empty_results_marker(soup):
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
    canonical = soup.find("link", rel="canonical")
    title = soup.select_one("h1.info__title")
    if not canonical:
        raise BridgeError("invalid_content")
    segments = [segment for segment in urlsplit(canonical.get("href", "")).path.split("/") if segment]
    if len(segments) >= 3 and segments[:2] == ["imovel", match.group(1)] and title and title.get_text(strip=True) and soup.find(id="desc_descricao"):
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
        location=LocationCriteria(arguments.get("city", "timoteo"), arguments.get("neighborhood"), tuple(arguments.get("neighborhood_ids", []))),
        filters=FilterBundle(PriceRange(arguments.get("minimum_price"), arguments.get("maximum_price")), AreaRange(arguments.get("minimum_area"), arguments.get("maximum_area"))),
        features=FeatureBundle(rooms, facilities),
        sort_order=SortOrder(arguments.get("sort_order", "")),
        page=PageNumber(arguments.get("page", 1)),
        reference_code=arguments.get("reference_code"),
    )


def _service(http_client):
    transport = TransportCoordinator(_GuardedHttpClient(http_client), UrlBuilder())
    return HelenaResearchService(transport=transport)


def _location_text(location):
    return ", ".join(value for value in (location["neighborhood"], location["city"]) if value)


def _listing_display(item):
    return {"reference": item["identity"]["property_id"], "url": item["url"], "title": item["title"], "location": _location_text(item["location"]), "price": item["price_text"]}


def _safe_search(native):
    for item in native["items"]:
        item["url"] = safe_url(item["url"], PROVIDER)
    return native


def _search(arguments):
    criteria = _criteria(arguments)
    with managed_httpx() as http_client:
        results = _service(http_client).search_rentals(criteria)
    native = _safe_search(results.to_dictionary())
    return {"native": native, "display": [_listing_display(item) for item in native["items"]]}


def _overview(detail):
    item = detail.overview
    return {"property_id": item.property_id, "title": item.title, "reference_code": item.reference_code, "description": item.description}


def _pricing(detail):
    item = detail.pricing
    return {"amount": item.amount, "condo_fee": item.condo_fee, "iptu": item.iptu, "currency": item.currency, "formatted_text": item.formatted_text}


def _location(detail):
    item = detail.location
    return {"address": item.address, "neighborhood": item.neighborhood, "city": item.city, "state": item.state}


def _specifications(detail):
    item = detail.specs
    return {"bedrooms": item.bedrooms, "suites": item.suites, "bathrooms": item.bathrooms, "parking_spaces": item.parking_spaces, "usable_area": item.usable_area}


def _detail_native(detail):
    return {"overview": _overview(detail), "pricing": _pricing(detail), "location": _location(detail), "specs": _specifications(detail), "characteristics": list(detail.characteristics), "photos": list(detail.photos), "canonical_url": safe_url(detail.canonical_url, PROVIDER)}


def _detail(arguments):
    reference = arguments["reference"]
    if not re.fullmatch(r"[0-9]{1,20}", reference):
        raise BridgeError("invalid_input")
    with managed_httpx() as http_client:
        result = _service(http_client).get_property_detail(reference)
    native = _detail_native(result)
    location = _location(result)
    display = [{"reference": reference, "url": native["canonical_url"], "title": native["overview"]["title"], "location": _location_text(location), "price": native["pricing"]["amount"]}]
    return {"native": native, "display": display}


def execute(operation: str, arguments: dict) -> dict:
    """Run rental search or property detail; Helena has no facets operation."""
    if not isinstance(arguments, dict):
        raise BridgeError("invalid_input")
    if operation == "search" and not set(arguments) - _ALLOWED_FILTERS:
        return _search(arguments)
    if operation == "detail" and set(arguments) == {"reference"}:
        return _detail(arguments)
    if operation == "facets":
        raise BridgeError("unsupported_capability")
    raise BridgeError("invalid_input")
