"""Ordering of the merged search result by total monthly price, before the page is cut."""

from __future__ import annotations

from typing import Any


def order_by_total_price(items: list[dict[str, Any]], descending: bool) -> list[dict[str, Any]]:
    """Sort by total_price in the requested direction; listings without a price always go last."""
    priced = [item for item in items if item.get("total_price") is not None]
    unpriced = [item for item in items if item.get("total_price") is None]
    ordered = sorted(priced, key=_total_price, reverse=descending)
    return ordered + unpriced


def _total_price(item: dict[str, Any]) -> float:
    return float(item["total_price"])
