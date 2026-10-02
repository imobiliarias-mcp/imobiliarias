"""Bridge adapter for Imovelweb's existing HTML provider."""

import json
from typing import Any
from urllib.parse import urlsplit

from scripts.client.configuration import ImovelwebConfiguration
from scripts.client.http_transport import HttpTransport
from scripts.client.parsers import FacetParser
from scripts.client.query_builder import ImovelwebQueryBuilder
from scripts.domain.criteria import RentalFilter
from scripts.domain.exceptions import TransportException
from scripts.domain.value_objects import PropertyCode
from scripts.providers.imovelweb import ImovelwebRentalProvider

from rental_bridge.errors import BridgeError
from rental_bridge.providers.imovelweb_identity import validate_page_identity
from rental_bridge.transport.safe_http import ensure_response, managed_httpx, safe_url

PROVIDER = "imovelweb"


class GuardedHttpxClient:
    """Guard source HTTP responses and page identity before HTML parsing."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.guard_error: BridgeError | None = None

    def get(self, url: str) -> Any:
        try:
            response = ensure_response(self._client.get(_https_source_url(url)))
            validate_page_identity(response.text, url)
            return response
        except BridgeError as error:
            self.guard_error = error
            raise


def _https_source_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.imovelweb.com.br", "imovelweb.com.br"}:
        raise BridgeError("invalid_input")
    return url


def _source_provider(client: Any) -> tuple[ImovelwebRentalProvider, GuardedHttpxClient]:
    configuration = ImovelwebConfiguration()
    guarded_client = GuardedHttpxClient(client)
    transport = HttpTransport(guarded_client)
    builder = ImovelwebQueryBuilder(configuration)
    provider = ImovelwebRentalProvider(transport=transport, query_builder=builder)
    return provider, guarded_client


def _search_filter(arguments: dict[str, Any]) -> RentalFilter:
    criteria = RentalFilter()
    if arguments.get("city"):
        criteria = criteria.with_city(arguments["city"])
    if arguments.get("neighborhood"):
        criteria = criteria.with_neighborhood(arguments["neighborhood"])
    if arguments.get("property_type"):
        criteria = criteria.with_property_type(arguments["property_type"])
    if "bedrooms" in arguments:
        criteria = criteria.with_bedrooms(arguments["bedrooms"])
    if "sort" in arguments:
        criteria = criteria.with_sort(arguments["sort"])
    if "page" in arguments:
        criteria = criteria.with_page(arguments["page"])
    return criteria


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _display_item(item: dict[str, Any]) -> dict[str, Any]:
    location = ", ".join(part for part in (item.get("locality"), item.get("street")) if part)
    projection = {
        "reference": item.get("code"),
        "url": item.get("url"),
        "title": item.get("title"),
        "location": location,
        "price": item.get("rental_price_formatted"),
    }
    display = {key: value for key, value in projection.items() if value is not None and value != ""}
    if "url" in display:
        display["url"] = safe_url(display["url"], PROVIDER)
    return display


def _search(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    provider, guarded_client = _source_provider(client)
    response = _run_source(lambda: provider.search_rentals(_search_filter(arguments)), guarded_client)
    native = response.to_dictionary()
    display = [_display_item(item) for item in native["listings"]]
    return {"native": _json_safe(native), "display": _json_safe(display)}


def _detail(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    reference = arguments["reference"]
    if not reference.isdigit():
        raise BridgeError("invalid_input")
    provider, guarded_client = _source_provider(client)
    detail = _run_source(
        lambda: provider.get_property_detail(PropertyCode(reference)), guarded_client
    )
    native = detail.to_dictionary()
    native["url"] = safe_url(native["url"], PROVIDER)
    return {"native": _json_safe(native), "display": [_json_safe(_display_item(native))]}


def _facets(client: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    builder = ImovelwebQueryBuilder(ImovelwebConfiguration())
    url = builder.build_facets_url()
    response = _fetch_guarded(client, url)
    facets = FacetParser().parse_facets_response(response.text).to_dictionary()
    selected = arguments["selector"]
    if selected == "all":
        native = facets
    if selected != "all":
        native = {selected: facets[selected]}
    return {"native": _json_safe(native), "display": []}


def _fetch_guarded(client: Any, url: str) -> Any:
    guarded = GuardedHttpxClient(client)
    try:
        return guarded.get(url)
    except BridgeError:
        raise
    except Exception as error:
        raise BridgeError("worker_error") from error


def _run_source(operation: Any, guarded_client: GuardedHttpxClient) -> Any:
    try:
        return operation()
    except Exception as error:
        if guarded_client.guard_error is not None:
            raise guarded_client.guard_error from error
        if isinstance(error, TransportException):
            raise BridgeError("http_error") from error
        raise BridgeError("worker_error") from error


def _validate(operation: str, arguments: dict[str, Any]) -> None:
    if operation not in {"search", "detail", "facets"} or not isinstance(arguments, dict):
        raise BridgeError("invalid_input")
    allowed = {"city", "neighborhood", "property_type", "bedrooms", "sort", "page"}
    if operation == "detail":
        allowed = {"reference"}
        if not isinstance(arguments.get("reference"), str) or not arguments["reference"].strip():
            raise BridgeError("invalid_input")
    if operation == "facets":
        allowed = {"selector"}
        if arguments.get("selector") not in {"all", "neighborhoods", "property_types", "sort_orders"}:
            raise BridgeError("invalid_input")
    if set(arguments) - allowed:
        raise BridgeError("invalid_input")


def _execute_with_client(operation: str, arguments: dict[str, Any], client: Any) -> dict[str, Any]:
    if operation == "search":
        return _search(client, arguments)
    if operation == "detail":
        return _detail(client, arguments)
    return _facets(client, arguments)


def execute(operation: str, arguments: dict[str, Any], *, client: Any = None) -> dict[str, Any]:
    """Execute search, detail, or facets with verified HTTP and no redirects."""
    _validate(operation, arguments)
    if client is not None:
        return _execute_with_client(operation, arguments, client)
    with managed_httpx(timeout=20.0) as owned_client:
        return _execute_with_client(operation, arguments, owned_client)
