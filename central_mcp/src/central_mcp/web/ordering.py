"""Ordering of merged search results so that every agency is represented on the first page."""

from __future__ import annotations

from itertools import zip_longest
from typing import Any


def interleave_by_provider(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Round-robin across providers, keeping each provider's own order, then cut to limit."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in results:
        buckets.setdefault(str(item.get("provider", "")), []).append(item)
    rounds = zip_longest(*buckets.values())
    interleaved = [item for row in rounds for item in row if item is not None]
    return interleaved[:limit]
