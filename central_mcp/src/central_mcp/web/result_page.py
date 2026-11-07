"""One page of an ordered search result, with the figures the browser needs to keep paging."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResultPage:
    """Items of one page plus the total across all pages and whether another page follows."""

    items: list[Any]
    page: int
    page_size: int
    total: int
    has_more: bool


def take_page(items: list[Any], page: int, page_size: int) -> ResultPage:
    """Return the 1-based page of items; a page past the end is empty and has no successor."""
    start = (page - 1) * page_size
    end = start + page_size
    return ResultPage(
        items=items[start:end],
        page=page,
        page_size=page_size,
        total=len(items),
        has_more=end < len(items),
    )
