"""Minimum-rent filter applied by the central service after the providers answer."""

from __future__ import annotations

from typing import Any

RENT_PRICE_KEY = "rent_price"


def apply_minimum_price(listings: list[dict[str, Any]], minimum: float | None) -> list[dict[str, Any]]:
    """Keep listings whose rent is at least the minimum; with a minimum, unpriced listings are dropped."""
    if minimum is None:
        return list(listings)
    return [listing for listing in listings if _meets_minimum(listing.get(RENT_PRICE_KEY), minimum)]


def _meets_minimum(rent: Any, minimum: float) -> bool:
    if not isinstance(rent, (int, float)):
        return False
    return rent >= minimum
