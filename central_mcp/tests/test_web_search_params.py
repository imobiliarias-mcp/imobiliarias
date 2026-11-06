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
