"""HTTP response guards for Cabral Porto Tecimob endpoints."""

import re
from typing import Any

from cabralporto_research.infrastructure.http_client import HttpResponse

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response

API_PREFIX = "/api/"
SEARCH_PATH = "/api/properties"
FACET_PATHS = {
    "/api/filters/states",
    "/api/filters/neighborhoods",
    "/api/filters/types",
}


class SafeTransport:
    """Adapt a managed bridge client to Tecimob's core transport contract."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def get(self, url: str, params: dict[str, str] | None = None) -> HttpResponse:
        headers = {"x-domain": "cabralportoimoveis.com.br", "Accept": "application/json"}
        response = ensure_response(self._client.get(url, params=params, headers=headers))
        payload = _decode_response(response)
        _require_payload(response.url.path, payload)
        return HttpResponse(response.status_code, response.text, payload, str(response.url))


def _decode_response(response: Any) -> Any:
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        raise BridgeError("invalid_content")
    try:
        return response.json()
    except ValueError as error:
        raise BridgeError("invalid_content") from error


def _require_payload(path: str, payload: Any) -> None:
    if path == SEARCH_PATH and _is_search_payload(payload):
        return
    if path in FACET_PATHS and _is_facet_payload(path, payload):
        return
    if re.fullmatch(r"/api/properties/[^/]+", path) and _is_detail_payload(payload):
        return
    raise BridgeError("invalid_content")


def _is_search_payload(payload: Any) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return False
    return all(_is_search_record(item) for item in payload["data"])


def _is_search_record(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    return bool(item.get("id")) and bool(item.get("reference")) and _has_text(item.get("url"))


def _is_facet_payload(path: str, payload: Any) -> bool:
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return False
    return all(_is_facet_record(path, item) for item in payload["data"])


def _is_facet_record(path: str, item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if path.endswith("/states"):
        return isinstance(item.get("cities"), list) and _has_text(item.get("acronym"))
    label = _facet_record_label(path, item)
    return bool(item.get("id")) and _has_text(label)


def _facet_record_label(path: str, item: dict[str, Any]) -> Any:
    if path.endswith("/types"):
        return item.get("title")
    return item.get("name")


def _is_detail_payload(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    item = payload.get("data")
    if not isinstance(item, dict):
        return False
    return bool(item.get("id")) and bool(item.get("reference")) and _has_text(item.get("url"))


def _has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
