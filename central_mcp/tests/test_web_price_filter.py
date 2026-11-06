"""Tests for the central rent-range filter applied to browser search results."""

from central_mcp.web.price_filter import apply_rent_range


def _listing(code: str, rent_price: float | None) -> dict:
    return {"provider": "vivareal", "code": code, "rent_price": rent_price}


def _codes(listings: list[dict]) -> list[str]:
    return [listing["code"] for listing in listings]


def test_without_bounds_every_listing_is_kept_including_unpriced():
    listings = [_listing("a", 500.0), _listing("b", None)]
    assert _codes(apply_rent_range(listings, None, None)) == ["a", "b"]


def test_no_listings_yield_no_listings():
    assert apply_rent_range([], 1000.0, 2000.0) == []


def test_single_listing_at_or_above_the_minimum_is_kept():
    assert _codes(apply_rent_range([_listing("a", 1000.0)], 1000.0, None)) == ["a"]


def test_single_listing_below_the_minimum_is_dropped():
    assert apply_rent_range([_listing("a", 999.0)], 1000.0, None) == []


def test_single_listing_at_or_below_the_maximum_is_kept():
    assert _codes(apply_rent_range([_listing("a", 1500.0)], None, 1500.0)) == ["a"]


def test_single_listing_above_the_maximum_is_dropped():
    assert apply_rent_range([_listing("a", 1500.01)], None, 1500.0) == []


def test_many_listings_keep_only_those_inside_the_range_in_order():
    listings = [_listing("a", 900.0), _listing("b", 1200.0), _listing("c", 1800.0), _listing("d", 1100.0)]
    assert _codes(apply_rent_range(listings, 1000.0, 1500.0)) == ["b", "d"]


def test_listing_without_a_price_is_dropped_when_a_minimum_is_set():
    assert apply_rent_range([_listing("a", None)], 500.0, None) == []


def test_listing_without_a_price_is_dropped_when_a_maximum_is_set():
    assert apply_rent_range([_listing("a", None)], None, 1500.0) == []


def test_non_numeric_price_is_treated_as_unpriced():
    listings = [{"code": "a", "rent_price": "1200"}]
    assert apply_rent_range(listings, None, 1500.0) == []


def test_zero_minimum_keeps_priced_listings_and_drops_unpriced_ones():
    listings = [_listing("a", 0.0), _listing("b", None)]
    assert _codes(apply_rent_range(listings, 0.0, None)) == ["a"]


def test_input_list_is_not_mutated():
    listings = [_listing("a", 1000.0), _listing("b", 2000.0)]
    apply_rent_range(listings, 500.0, 1500.0)
    assert _codes(listings) == ["a", "b"]
