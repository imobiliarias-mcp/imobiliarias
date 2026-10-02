"""Verified transport and page identity checks for Márcio Imóveis."""

from typing import Any
from urllib.parse import urlsplit

from marcio_research.client.configuration import PortalConfiguration
from marcio_research.client.http_transport import HttpResponse

from rental_bridge.errors import BridgeError
from rental_bridge.transport.safe_http import ensure_response


class VerifiedHttpxTransport:
    """Adapt verified httpx requests to Márcio's injectable transport protocol."""

    def __init__(self, client: Any, configuration: PortalConfiguration) -> None:
        self._client = client
        self._configuration = configuration

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        target = _source_url(url, self._configuration.base_url)
        response = ensure_response(self._client.get(target, headers=headers, follow_redirects=False))
        _validate_html(response.text, target, self._configuration)
        return HttpResponse(response.status_code, response.text, str(response.url))

    def post(self, url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> HttpResponse:
        target = _source_url(url, self._configuration.base_url)
        response = ensure_response(
            self._client.post(target, data=data, headers=headers, follow_redirects=False)
        )
        _validate_html(response.text, target, self._configuration)
        return HttpResponse(response.status_code, response.text, str(response.url))


def _source_url(url: str, base_url: str) -> str:
    parsed = urlsplit(url)
    base = urlsplit(base_url)
    if parsed.scheme != "https" or parsed.hostname != base.hostname or parsed.port:
        raise BridgeError("invalid_input")
    return url


def _validate_html(html: str, url: str, configuration: PortalConfiguration) -> None:
    path = urlsplit(url).path
    if path.startswith(("/imovel/", "/propriedade/")):
        _validate_property_page_identity(html)
        return
    if path.startswith((configuration.search_path, "/properties-search/")):
        _validate_search_page_identity(html)
        return
    if "realhomesLocationsData" not in html and "<select" not in html:
        raise BridgeError("invalid_content")


def _validate_property_page_identity(html: str) -> None:
    if "rh_page__title" not in html or "rh_content" not in html:
        raise BridgeError("invalid_content")


def _validate_search_page_identity(html: str) -> None:
    markers = (
        "rh_pagination__stats",
        "rh_prop_card",
        "rh_list_card",
        "realhomesLocationsData",
        "<select",
    )
    if not any(marker in html for marker in markers):
        raise BridgeError("invalid_content")
