"""Page identity checks for Imovelweb responses before source parsing."""

import re
from urllib.parse import urlsplit

from rental_bridge.errors import BridgeError


def validate_page_identity(html: str, url: str) -> None:
    path = urlsplit(url).path
    if path.startswith("/propriedades/"):
        _validate_detail_identity(html, path)
        return
    if not _has_search_identity(html):
        raise BridgeError("invalid_content")


def _validate_detail_identity(html: str, path: str) -> None:
    expected_code = _detail_code(path)
    if expected_code is None or not _has_detail_identity(html, expected_code):
        raise BridgeError("invalid_content")


def _detail_code(path: str) -> str | None:
    match = re.search(r"-(\d+)\.html$", path)
    if match is None:
        return None
    return match.group(1)


def _has_detail_identity(html: str, expected_code: str) -> bool:
    identifier = re.search(r"['\"]?idAviso['\"]?\s*:\s*['\"]?(\d+)", html)
    if identifier is None or identifier.group(1) != expected_code:
        return False
    metadata = re.search(r"<meta\b[^>]*property=[\"']og:url[\"'][^>]*>", html, re.IGNORECASE)
    if metadata is None:
        return False
    content = re.search(r"\bcontent=[\"']([^\"']+)", metadata.group(), re.IGNORECASE)
    if content is None:
        return False
    return urlsplit(content.group(1)).path.endswith(f"-{expected_code}.html")


def _has_search_identity(html: str) -> bool:
    if re.search(
        r"<h1\b(?=[^>]*class=[\"'][^\"']*postingsTitle-module__title[^\"']*[\"'])[^>]*>\s*\d+\s+Im[oó]veis\b",
        html,
        re.IGNORECASE,
    ):
        return True
    return re.search(
        r"<[^>]+(?=[^>]*data-qa=[\"']posting PROPERTY[\"'])(?=[^>]*data-id=[\"']\d+[\"'])(?=[^>]*data-posting-type=[\"']PROPERTY[\"'])[^>]*>",
        html,
        re.IGNORECASE,
    ) is not None
