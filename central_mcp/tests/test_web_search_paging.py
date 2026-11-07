"""Tests for /api/search paging: one cached fan-out serves every page, ordering is global, details are per page."""

from typing import Any

import pytest
from starlette.testclient import TestClient

from central_mcp.config import AppConfig
from central_mcp.http_app import create_http_app
from central_mcp.server import create_mcp_server

TOTAL = 30


def _price_for(index: int) -> float:
    """Scatter prices so the cheapest listing is not the first one the provider returned."""
    return 1000.0 + ((index * 7) % TOTAL) * 10


class PagedService:
    """Counts fan-outs and detail calls; returns TOTAL listings at distinct prices."""

    def __init__(self, provider_status: str = "ok") -> None:
        self.provider_status = provider_status
        self.search_calls = 0
        self.search_kwargs: dict[str, Any] = {}
        self.detail_calls = 0

    def catalog(self) -> list[dict[str, Any]]:
        return []

    async def federated_search(self, **kwargs: Any) -> dict[str, Any]:
        self.search_calls += 1
        self.search_kwargs = kwargs
        results = [_projected(index) for index in range(TOTAL)]
        provider = {"provider": "vivareal", "status": self.provider_status, "count": TOTAL, "error_code": None, "error": None}
        return {"status": self.provider_status, "providers": [provider], "results": results}

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        self.detail_calls += 1
        return {"photos": [], "description": None}

    async def facets(self, provider: str) -> dict[str, Any]:
        return {}


def _projected(index: int) -> dict[str, Any]:
    price = _price_for(index)
    return {
        "provider": "vivareal",
        "code": str(index),
        "title": f"Imóvel {index}",
        "location": "Centro, Timóteo",
        "rent_price": price,
        "condo_fee": None,
        "iptu": None,
        "total_price": price,
        "bedrooms": 2,
        "url": f"https://www.vivareal.com.br/imovel/{index}",
    }


def _client(service: PagedService, ttl: float = 600.0) -> TestClient:
    config = AppConfig(rate_limit_burst=1000, rate_limit_per_minute=100000, search_cache_ttl_seconds=ttl)
    return TestClient(create_http_app(create_mcp_server(), config, service=service))


def _codes(body: dict[str, Any]) -> list[str]:
    return [listing["code"] for listing in body["results"]]


def test_first_page_is_the_twelve_cheapest_listings():
    with _client(PagedService()) as client:
        body = client.get("/api/search").json()
    expected = sorted(range(TOTAL), key=_price_for)[:12]
    assert _codes(body) == [str(index) for index in expected]
    assert (body["page"], body["page_size"], body["total"], body["has_more"]) == (1, 12, TOTAL, True)


def test_last_page_has_the_remainder_and_no_more():
    with _client(PagedService()) as client:
        body = client.get("/api/search", params={"page": "3"}).json()
    assert len(body["results"]) == 6
    assert body["has_more"] is False


def test_page_past_the_end_is_empty():
    with _client(PagedService()) as client:
        body = client.get("/api/search", params={"page": "9"}).json()
    assert body["results"] == []
    assert body["has_more"] is False


def test_later_pages_reuse_the_first_fan_out():
    service = PagedService()
    with _client(service) as client:
        client.get("/api/search")
        client.get("/api/search", params={"page": "2"})
        client.get("/api/search", params={"page": "3"})
    assert service.search_calls == 1


def test_page_number_is_not_forwarded_to_providers():
    service = PagedService()
    with _client(service) as client:
        client.get("/api/search", params={"page": "3"})
    assert service.search_kwargs["page"] == 1


def test_only_the_listings_on_the_page_are_enriched():
    service = PagedService()
    with _client(service) as client:
        client.get("/api/search")
    assert service.detail_calls == 12


def test_sort_desc_puts_the_most_expensive_first():
    with _client(PagedService()) as client:
        body = client.get("/api/search", params={"sort": "total_desc"}).json()
    expected = sorted(range(TOTAL), key=_price_for, reverse=True)[:12]
    assert _codes(body) == [str(index) for index in expected]


def test_invalid_sort_is_rejected_with_a_portuguese_message():
    with _client(PagedService()) as client:
        response = client.get("/api/search", params={"sort": "nope"})
    assert response.status_code == 400
    assert "sort deve ser" in response.json()["error"]


def test_changing_neighborhood_or_min_price_reuses_the_cache():
    service = PagedService()
    with _client(service) as client:
        client.get("/api/search")
        client.get("/api/search", params={"neighborhoods": "bairro-que-nao-existe"})
        client.get("/api/search", params={"min_price": "1200", "sort": "total_desc"})
    assert service.search_calls == 1


def test_changing_max_price_fetches_again_because_providers_filter_on_it():
    service = PagedService()
    with _client(service) as client:
        client.get("/api/search")
        client.get("/api/search", params={"max_price": "1500"})
    assert service.search_calls == 2


def test_refresh_ignores_the_cached_outcome():
    service = PagedService()
    with _client(service) as client:
        client.get("/api/search")
        client.get("/api/search", params={"refresh": "1"})
    assert service.search_calls == 2


def test_error_outcomes_are_not_cached():
    service = PagedService(provider_status="error")
    with _client(service) as client:
        first = client.get("/api/search").json()
        client.get("/api/search")
    assert first["status"] == "error"
    assert service.search_calls == 2


def test_zero_ttl_disables_reuse_across_requests():
    service = PagedService()
    with _client(service, ttl=0.0) as client:
        client.get("/api/search")
        client.get("/api/search", params={"page": "2"})
    assert service.search_calls == 2


def test_refresh_rejects_non_boolean_values():
    with _client(PagedService()) as client:
        response = client.get("/api/search", params={"refresh": "talvez"})
    assert response.status_code == 400


@pytest.mark.parametrize("params", [{"page": "0"}, {"limit": "0"}])
def test_paging_parameters_still_validated(params):
    with _client(PagedService()) as client:
        assert client.get("/api/search", params=params).status_code == 400
