"""Tests for parsing price text typed in the browser, including Brazilian number formats."""

import pytest

from central_mcp.web.search_params import parse_search_params


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1500", 1500.0),
        ("1500,00", 1500.0),
        ("1500,5", 1500.5),
        ("1.500,00", 1500.0),
        ("1.500", 1500.0),
        ("1.500.000", 1500000.0),
        ("R$ 1.500,00", 1500.0),
        ("1500.5", 1500.5),
        ("0", 0.0),
    ],
)
def test_price_accepts_brazilian_and_plain_formats(raw, expected):
    assert parse_search_params({"max_price": raw})["max_price"] == expected


@pytest.mark.parametrize("raw", ["abc", "-1", "nan", "inf", "1500,", "1,2,3", "1_000", "1.5.00", "R$"])
def test_price_rejects_invalid_text(raw):
    with pytest.raises(ValueError, match="max_price"):
        parse_search_params({"max_price": raw})


def test_blank_price_means_no_price_filter():
    assert parse_search_params({"max_price": "   "})["max_price"] is None


def test_default_page_size_is_twelve():
    assert parse_search_params({})["limit"] == 12


def test_page_is_the_central_page_number_defaulting_to_first():
    assert parse_search_params({})["page"] == 1
    assert parse_search_params({"page": "3"})["page"] == 3


def test_sort_defaults_to_lowest_total_price():
    assert parse_search_params({})["sort"] == "total_asc"


@pytest.mark.parametrize("raw", ["total_asc", "total_desc"])
def test_sort_accepts_supported_orders(raw):
    assert parse_search_params({"sort": raw})["sort"] == raw


@pytest.mark.parametrize("raw", ["rent_asc", "TOTAL_ASC", "random"])
def test_sort_rejects_unknown_order_in_portuguese(raw):
    with pytest.raises(ValueError, match="sort deve ser"):
        parse_search_params({"sort": raw})


def test_refresh_defaults_to_false_and_accepts_flags():
    assert parse_search_params({})["refresh"] is False
    assert parse_search_params({"refresh": "1"})["refresh"] is True
    assert parse_search_params({"refresh": "true"})["refresh"] is True
    assert parse_search_params({"refresh": "0"})["refresh"] is False


def test_refresh_rejects_other_values():
    with pytest.raises(ValueError, match="refresh deve ser"):
        parse_search_params({"refresh": "sim"})
