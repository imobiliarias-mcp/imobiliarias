"""Tests for slicing an ordered result into pages with total and has_more."""

from central_mcp.web.result_page import take_page


def test_first_page_holds_the_first_slice_and_reports_more():
    page = take_page(list(range(30)), page=1, page_size=12)
    assert page.items == list(range(12))
    assert (page.page, page.page_size, page.total, page.has_more) == (1, 12, 30, True)


def test_last_partial_page_has_no_more():
    page = take_page(list(range(30)), page=3, page_size=12)
    assert page.items == list(range(24, 30))
    assert page.has_more is False


def test_page_past_the_end_is_empty_without_more():
    page = take_page(list(range(5)), page=4, page_size=12)
    assert page.items == []
    assert (page.total, page.has_more) == (5, False)


def test_empty_result_has_zero_total():
    page = take_page([], page=1, page_size=12)
    assert (page.items, page.total, page.has_more) == ([], 0, False)


def test_exact_multiple_has_no_extra_empty_page():
    page = take_page(list(range(24)), page=2, page_size=12)
    assert page.items == list(range(12, 24))
    assert page.has_more is False
