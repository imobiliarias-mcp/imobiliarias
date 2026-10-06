"""Provider capabilities matrix and request validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from central_mcp.errors import ProviderError, ProviderErrorCode


@dataclass(frozen=True)
class ProviderCapability:
    """Declared capabilities and availability for an agency provider."""

    provider_id: str
    supported_filters: frozenset[str]
    is_available: bool = True
    unavailable_reason: str = ""


PROVIDER_CAPABILITIES: dict[str, ProviderCapability] = {
    "alecorretoramg": ProviderCapability(
        "alecorretoramg",
        frozenset({"city", "min_price", "max_price", "bedrooms", "page"}),
    ),
    "arthusoimoveis": ProviderCapability(
        "arthusoimoveis",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "cabralporto": ProviderCapability(
        "cabralporto",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "casalinhares": ProviderCapability(
        "casalinhares",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "epifanioimoveis": ProviderCapability(
        "epifanioimoveis",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "helenaimoveis": ProviderCapability(
        "helenaimoveis",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "imobiliariaportalmg": ProviderCapability(
        "imobiliariaportalmg",
        frozenset({"city", "min_price", "max_price", "bedrooms", "page"}),
    ),
    "imobiliariavaleinvest": ProviderCapability(
        "imobiliariavaleinvest",
        frozenset({"city", "min_price", "max_price", "bedrooms", "property_type", "page"}),
    ),
    "imovelweb": ProviderCapability(
        "imovelweb",
        frozenset({"city", "bedrooms", "property_type", "page"}),
        is_available=False,
        unavailable_reason="Browser required (Cloudflare/Patchright)",
    ),
    "marcioimoveis": ProviderCapability(
        "marcioimoveis",
        frozenset({"city", "min_price", "max_price", "bedrooms", "property_type", "page"}),
    ),
    "minascaixaimoveis": ProviderCapability(
        "minascaixaimoveis",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "niltoncorretordeimoveis": ProviderCapability(
        "niltoncorretordeimoveis",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "novaimobiliaria": ProviderCapability(
        "novaimobiliaria",
        frozenset({"city", "max_price", "bedrooms", "page"}),
    ),
    "veraimobiliaria": ProviderCapability(
        "veraimobiliaria",
        frozenset({"city", "min_price", "max_price", "bedrooms", "page"}),
    ),
    "vivareal": ProviderCapability(
        "vivareal",
        frozenset({"city", "min_price", "max_price", "bedrooms", "page"}),
    ),
}


def get_provider_capability(provider_id: str) -> ProviderCapability:
    """Lookup capability record or return default for custom registered providers."""
    if provider_id not in PROVIDER_CAPABILITIES:
        return ProviderCapability(
            provider_id=provider_id,
            supported_filters=frozenset(
                {"city", "min_price", "max_price", "bedrooms", "property_type", "page"}
            ),
        )
    return PROVIDER_CAPABILITIES[provider_id]


def validate_provider_filters(provider_id: str, filters: Mapping[str, Any]) -> None:
    """Validate that the given provider supports all requested active filters."""
    cap = get_provider_capability(provider_id)
    _check_active_filters(provider_id, cap, filters)
    _check_vale_invest_rules(provider_id, filters)


def _check_active_filters(
    provider_id: str, cap: ProviderCapability, filters: Mapping[str, Any]
) -> None:
    for name, value in filters.items():
        if value is None or value == "" or value == 0:
            continue
        if name not in cap.supported_filters:
            msg = f"Provider {provider_id} does not support filter '{name}'"
            raise ProviderError(provider_id, ProviderErrorCode.UNSUPPORTED_FILTER, msg)


def _check_vale_invest_rules(provider_id: str, filters: Mapping[str, Any]) -> None:
    if provider_id != "imobiliariavaleinvest":
        return
    min_p = filters.get("min_price")
    max_p = filters.get("max_price")
    has_min = min_p is not None and float(min_p) > 0
    has_max = max_p is not None and float(max_p) > 0
    if has_min and not has_max:
        msg = "imobiliariavaleinvest min_price requires max_price"
        raise ProviderError(provider_id, ProviderErrorCode.UNSUPPORTED_FILTER, msg)


def validate_search_request(
    city: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    bedrooms: int | None = None,
    property_type: str | None = None,
    page: int = 1,
    providers: list[str] | None = None,
    known_providers: set[str] | None = None,
) -> None:
    """Validate numerical and string bounds for search request."""
    _validate_page(page)
    _validate_prices(min_price, max_price)
    _validate_bedrooms(bedrooms)
    _validate_strings(city, property_type)
    if providers is not None:
        _validate_provider_list(providers, known_providers)


def _validate_page(page: int) -> None:
    if page < 1:
        raise ValueError("page must be >= 1")


def _validate_prices(min_price: float | None, max_price: float | None) -> None:
    if min_price is not None and min_price < 0:
        raise ValueError("min_price must be >= 0")
    if max_price is not None and max_price < 0:
        raise ValueError("max_price must be >= 0")
    if min_price is not None and max_price is not None and min_price > max_price:
        raise ValueError("min_price cannot exceed max_price")


def _validate_bedrooms(bedrooms: int | None) -> None:
    if bedrooms is not None and bedrooms < 0:
        raise ValueError("bedrooms must be >= 0")


def _validate_strings(city: str | None, property_type: str | None) -> None:
    if city is not None and len(city) > 100:
        raise ValueError("city length exceeds 100 characters")
    if property_type is not None and len(property_type) > 100:
        raise ValueError("property_type length exceeds 100 characters")


def _validate_provider_list(
    providers: list[str], known: set[str] | None = None
) -> None:
    if len(providers) > 15:
        raise ValueError(f"Maximum 15 providers allowed, got {len(providers)}")
    valid_set = known if known is not None else set(PROVIDER_CAPABILITIES.keys())
    seen: set[str] = set()
    for pid in providers:
        if pid in seen:
            raise ValueError(f"Duplicate provider requested: {pid}")
        seen.add(pid)
        if pid not in valid_set:
            raise ValueError(f"Unknown provider: {pid}")
