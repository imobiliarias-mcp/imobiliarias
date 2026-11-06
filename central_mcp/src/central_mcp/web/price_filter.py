"""Rent-range filter applied by the central service after the providers answer."""

from __future__ import annotations

from typing import Any

RENT_PRICE_KEY = "rent_price"


def apply_rent_range(
    listings: list[dict[str, Any]], minimum: float | None, maximum: float | None
) -> list[dict[str, Any]]:
    """Keep listings whose rent lies within the bounds; with any bound set, unpriced listings are dropped."""
    if minimum is None and maximum is None:
        return list(listings)
    return [listing for listing in listings if _within_range(listing.get(RENT_PRICE_KEY), minimum, maximum)]


def _within_range(rent: Any, minimum: float | None, maximum: float | None) -> bool:
    if not isinstance(rent, (int, float)):
        return False
    return _at_least(rent, minimum) and _at_most(rent, maximum)


def _at_least(rent: float, minimum: float | None) -> bool:
    return minimum is None or rent >= minimum


def _at_most(rent: float, maximum: float | None) -> bool:
    return maximum is None or rent <= maximum
