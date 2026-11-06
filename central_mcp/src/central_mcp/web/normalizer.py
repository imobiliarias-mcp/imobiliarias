"""Normalize provider-specific media, descriptions and links into one web shape.

Descriptions come from third-party sites and are untrusted: they are returned as
plain text, capped in length, and must be rendered as text (never as HTML).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

PHOTO_KEYS = ("photos", "images", "gallery")
PHOTO_URL_KEYS = ("url", "src", "href")
SINGLE_MEDIA_KEYS = ("media_url", "image_url", "cover_url")
DESCRIPTION_KEYS = ("description", "descricao")
MAX_DESCRIPTION_CHARS = 2000
ALLOWED_SCHEMES = frozenset({"http", "https"})


def normalize_http_url(value: Any) -> str | None:
    """Return the trimmed URL when it is an absolute http(s) link, otherwise None."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.netloc:
        return None
    return cleaned


def normalize_photos(raw: dict[str, Any]) -> tuple[str, ...]:
    """Collect unique valid photo URLs from the first provider key that has any."""
    for key in PHOTO_KEYS:
        urls = _collect_photo_urls(raw.get(key))
        if urls:
            return urls
    return ()


def normalize_description(raw: dict[str, Any]) -> str | None:
    """Return the first non-blank text description, trimmed and length-capped."""
    for key in DESCRIPTION_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:MAX_DESCRIPTION_CHARS]
    return None


def _collect_photo_urls(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    urls = (_photo_url(item) for item in value)
    unique = dict.fromkeys(url for url in urls if url is not None)
    return tuple(unique)


def _photo_url(item: Any) -> str | None:
    if isinstance(item, dict):
        return _first_photo_url_in(item)
    return normalize_http_url(item)


def _first_photo_url_in(item: dict[str, Any]) -> str | None:
    for key in PHOTO_URL_KEYS:
        url = normalize_http_url(item.get(key))
        if url is not None:
            return url
    return None


def normalize_cover_fallback(raw: dict[str, Any]) -> tuple[str, ...]:
    """Return the single cover image URL some search payloads carry, when it is valid."""
    for key in SINGLE_MEDIA_KEYS:
        url = normalize_http_url(raw.get(key))
        if url is not None:
            return (url,)
    return ()
