"""HTTP response guards for Arthuso endpoints."""

from typing import Any
from urllib.parse import urljoin

from arthuso.infrastructure.endpoints import BASE_URL
from bs4 import BeautifulSoup

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response

TAXONOMY_PATHS = {
    "/wp-json/wp/v2/property_city",
    "/wp-json/wp/v2/property_area",
    "/wp-json/wp/v2/property_type",
}
PROPERTIES_PATH = "/wp-json/wp/v2/properties"


class SafeTransport:
    """Adapt a bridge-managed client to Arthuso's transport protocol."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get_html(self, path_or_url: str, params: dict[str, Any]) -> str:
        response = self._get(path_or_url, params)
        _require_content_type(response, "text/html")
        _require_search_markup(response.text)
        return response.text

    def get_json(self, path_or_url: str, params: dict[str, Any]) -> Any:
        response = self._get(path_or_url, params)
        _require_content_type(response, "application/json")
        payload = _decode_json(response)
        _require_json_shape(response.url.path, params, payload)
        return payload

    def _get(self, path_or_url: str, params: dict[str, Any]) -> Any:
        base = f"{BASE_URL.rstrip('/')}/"
        url = urljoin(base, path_or_url.lstrip("/"))
        return ensure_response(self._client.get(url, params=params))


def _require_content_type(response: Any, expected: str) -> None:
    content_type = response.headers.get("content-type", "").lower()
    if expected not in content_type:
        raise BridgeError("invalid_content")


def _require_search_markup(html: str) -> None:
    document = BeautifulSoup(html, "html.parser")
    if document.select_one(".listing-view, .item-listing-wrap") is None:
        raise BridgeError("invalid_content")


def _decode_json(response: Any) -> Any:
    try:
        return response.json()
    except ValueError as error:
        raise BridgeError("invalid_content") from error


def _require_json_shape(path: str, parameters: dict[str, Any], payload: Any) -> None:
    if path in TAXONOMY_PATHS and _is_taxonomy_list(payload):
        return
    if path == PROPERTIES_PATH and "slug" in parameters and _is_property_list(payload):
        return
    if path.startswith(f"{PROPERTIES_PATH}/") and _is_property_record(payload):
        return
    raise BridgeError("invalid_content")


def _is_taxonomy_list(payload: Any) -> bool:
    if not isinstance(payload, list):
        return False
    return all(_is_taxonomy_record(item) for item in payload)


def _is_taxonomy_record(item: Any) -> bool:
    return isinstance(item, dict) and bool(item.get("id")) and bool(item.get("name"))


def _is_property_list(payload: Any) -> bool:
    if not isinstance(payload, list):
        return False
    return all(_is_property_record(item) for item in payload)


def _is_property_record(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    title = item.get("title")
    return bool(item.get("id")) and isinstance(title, dict) and bool(item.get("link"))
