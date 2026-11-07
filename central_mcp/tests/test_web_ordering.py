"""Tests for ordering the whole search result by total monthly price before paging."""

from central_mcp.web.ordering import order_by_total_price


def _item(code: str, total: float | None) -> dict:
    return {"provider": "a", "code": code, "total_price": total}


def _codes(items: list[dict]) -> list[str]:
    return [item["code"] for item in items]


def test_ascending_puts_cheapest_total_first():
    items = [_item("x", 2000.0), _item("y", 1000.0), _item("z", 1500.0)]
    assert _codes(order_by_total_price(items, descending=False)) == ["y", "z", "x"]


def test_descending_puts_most_expensive_total_first():
    items = [_item("x", 2000.0), _item("y", 1000.0), _item("z", 1500.0)]
    assert _codes(order_by_total_price(items, descending=True)) == ["x", "z", "y"]


def test_listings_without_total_price_go_last_in_both_directions():
    items = [_item("none", None), _item("cheap", 900.0), _item("dear", 3000.0)]
    assert _codes(order_by_total_price(items, descending=False)) == ["cheap", "dear", "none"]
    assert _codes(order_by_total_price(items, descending=True)) == ["dear", "cheap", "none"]


def test_equal_prices_keep_their_input_order_in_both_directions():
    items = [_item("first", 1000.0), _item("second", 1000.0)]
    assert _codes(order_by_total_price(items, descending=False)) == ["first", "second"]
    assert _codes(order_by_total_price(items, descending=True)) == ["first", "second"]


def test_empty_input_returns_empty():
    assert order_by_total_price([], descending=False) == []


def test_does_not_mutate_the_input_list():
    items = [_item("x", 2000.0), _item("y", 1000.0)]
    order_by_total_price(items, descending=False)
    assert _codes(items) == ["x", "y"]
