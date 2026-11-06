"""Tests for interleaving search results across providers before applying the page limit."""

from central_mcp.web.ordering import interleave_by_provider


def _item(provider: str, number: int) -> dict:
    return {"provider": provider, "code": str(number)}


def test_interleave_gives_every_provider_a_slot_in_the_first_page():
    results = [_item("a", 1), _item("a", 2), _item("a", 3), _item("b", 1), _item("c", 1)]
    picked = interleave_by_provider(results, limit=3)
    assert [(item["provider"], item["code"]) for item in picked] == [("a", "1"), ("b", "1"), ("c", "1")]


def test_interleave_keeps_each_providers_own_order():
    results = [_item("a", 1), _item("a", 2), _item("b", 1), _item("b", 2)]
    picked = interleave_by_provider(results, limit=10)
    assert [(item["provider"], item["code"]) for item in picked] == [("a", "1"), ("b", "1"), ("a", "2"), ("b", "2")]


def test_interleave_limit_larger_than_results_returns_all():
    results = [_item("a", 1), _item("b", 1)]
    assert len(interleave_by_provider(results, limit=50)) == 2


def test_interleave_empty_input_returns_empty():
    assert interleave_by_provider([], limit=5) == []


def test_interleave_single_provider_keeps_order():
    results = [_item("a", 1), _item("a", 2), _item("a", 3)]
    assert [item["code"] for item in interleave_by_provider(results, limit=2)] == ["1", "2"]
