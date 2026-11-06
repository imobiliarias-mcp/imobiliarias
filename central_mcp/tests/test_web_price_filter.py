"""Tests for the central minimum-rent filter applied to browser search results."""

from central_mcp.web.price_filter import apply_minimum_price


def _listing(code: str, rent_price: float | None) -> dict:
    return {"provider": "vivareal", "code": code, "rent_price": rent_price}


def _codes(listings: list[dict]) -> list[str]:
    return [listing["code"] for listing in listings]


def test_without_a_minimum_every_listing_is_kept_including_unpriced():
    listings = [_listing("a", 500.0), _listing("b", None)]
    assert _codes(apply_minimum_price(listings, None)) == ["a", "b"]


def test_no_listings_yield_no_listings():
    assert apply_minimum_price([], 1000.0) == []


def test_single_listing_at_or_above_the_minimum_is_kept():
    assert _codes(apply_minimum_price([_listing("a", 1000.0)], 1000.0)) == ["a"]


def test_single_listing_below_the_minimum_is_dropped():
    assert apply_minimum_price([_listing("a", 999.99)], 1000.0) == []


def test_many_listings_keep_only_those_at_or_above_the_minimum_in_order():
    listings = [_listing("a", 800.0), _listing("b", 1200.0), _listing("c", 1000.0), _listing("d", 900.0)]
    assert _codes(apply_minimum_price(listings, 1000.0)) == ["b", "c"]


def test_listing_without_a_price_is_dropped_when_a_minimum_is_set():
    listings = [_listing("a", None), _listing("b", 1500.0)]
    assert _codes(apply_minimum_price(listings, 1000.0)) == ["b"]


def test_non_numeric_price_is_treated_as_unpriced():
    listings = [{"provider": "vivareal", "code": "a", "rent_price": "1500"}]
    assert apply_minimum_price(listings, 1000.0) == []


def test_zero_minimum_keeps_priced_listings_and_drops_unpriced_ones():
    listings = [_listing("a", 0.0), _listing("b", None)]
    assert _codes(apply_minimum_price(listings, 0.0)) == ["a"]


def test_input_list_is_not_mutated():
    listings = [_listing("a", 500.0), _listing("b", 1500.0)]
    apply_minimum_price(listings, 1000.0)
    assert _codes(listings) == ["a", "b"]
