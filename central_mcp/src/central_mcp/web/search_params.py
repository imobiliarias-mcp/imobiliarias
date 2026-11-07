"""Validate raw /api query parameters into keyword arguments for the search service."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

DEFAULT_LIMIT = 12
MAX_LIMIT = 200
SUPPORTED_TRANSACTIONS = ("rent",)
DEFAULT_TRANSACTION = "rent"
SUPPORTED_SORTS = ("total_asc", "total_desc")
DEFAULT_SORT = "total_asc"


def parse_search_params(query: Mapping[str, str]) -> dict[str, Any]:
    """Return validated search arguments; city and neighborhoods stay raw for the route to resolve."""
    return {
        "providers": _csv(query.get("providers")),
        "city": _optional_text(query.get("city")),
        "neighborhoods": _csv(query.get("neighborhoods")) or [],
        "transaction": _transaction(query.get("transaction")),
        "min_price": _optional_price(query.get("min_price"), "min_price"),
        "max_price": _optional_price(query.get("max_price"), "max_price"),
        "bedrooms": _optional_int(query.get("bedrooms"), "bedrooms"),
        "property_type": _optional_text(query.get("property_type")),
        "page": _bounded_int(query.get("page"), "page", default=1, minimum=1, maximum=10_000),
        "limit": _bounded_int(query.get("limit"), "limit", default=DEFAULT_LIMIT, minimum=1, maximum=MAX_LIMIT),
        "sort": _sort(query.get("sort")),
        "refresh": _flag(query.get("refresh"), "refresh"),
    }


def required_text(query: Mapping[str, str], name: str) -> str:
    """Return a non-blank query parameter or raise ValueError naming it."""
    value = _optional_text(query.get(name))
    if value is None:
        raise ValueError(f"Missing required parameter: {name}")
    return value


def _transaction(raw: str | None) -> str:
    value = _optional_text(raw) or DEFAULT_TRANSACTION
    if value not in SUPPORTED_TRANSACTIONS:
        raise ValueError(f"transaction must be one of: {', '.join(SUPPORTED_TRANSACTIONS)}")
    return value


def _sort(raw: str | None) -> str:
    value = _optional_text(raw) or DEFAULT_SORT
    if value not in SUPPORTED_SORTS:
        raise ValueError(f"sort deve ser um de: {', '.join(SUPPORTED_SORTS)}")
    return value


def _flag(raw: str | None, name: str) -> bool:
    value = _optional_text(raw)
    if value is None:
        return False
    if value.lower() in ("1", "true"):
        return True
    if value.lower() in ("0", "false"):
        return False
    raise ValueError(f"{name} deve ser true ou false")


def _optional_text(raw: str | None) -> str | None:
    if raw is None or not raw.strip():
        return None
    return raw.strip()


def _csv(raw: str | None) -> list[str] | None:
    text = _optional_text(raw)
    if text is None:
        return None
    return [part.strip() for part in text.split(",") if part.strip()]


PRICE_PATTERN = re.compile(r"\d+(\.\d+)?")
THOUSANDS_PATTERN = re.compile(r"\d{1,3}(\.\d{3})+")


def _optional_price(raw: str | None, name: str) -> float | None:
    text = _optional_text(raw)
    if text is None:
        return None
    normalized = _normalize_price_text(text)
    if PRICE_PATTERN.fullmatch(normalized) is None:
        raise ValueError(f"{name} deve ser um valor numérico, ex.: 1500 ou 1.500,00")
    return float(normalized)


def _normalize_price_text(text: str) -> str:
    """Turn Brazilian (1.500,00, R$ 1.500) or plain (1500.5) price text into a plain decimal string."""
    stripped = text.replace("R$", "").strip()
    if "," in stripped:
        return stripped.replace(".", "").replace(",", ".")
    if THOUSANDS_PATTERN.fullmatch(stripped):
        return stripped.replace(".", "")
    return stripped


def _optional_int(raw: str | None, name: str) -> int | None:
    text = _optional_text(raw)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _bounded_int(raw: str | None, name: str, *, default: int, minimum: int, maximum: int) -> int:
    value = _optional_int(raw, name)
    if value is None:
        return default
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
