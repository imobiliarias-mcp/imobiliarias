"""Tests for location filters, the locations endpoint and transaction handling on /api routes."""

from typing import Any

from starlette.testclient import TestClient

from central_mcp.config import AppConfig
from central_mcp.http_app import create_http_app
from central_mcp.server import create_mcp_server


def _listing(index: int, location: str | None, provider: str = "vivareal") -> dict[str, Any]:
    return {
        "provider": provider,
        "code": f"{provider}-{index}",
        "title": f"Imóvel {index}",
        "location": location,
        "rent_price": 1000.0 + index,
        "url": f"https://example.test/{provider}/{index}",
        "raw": {},
    }


class LocatedService:
    """Returns fixed federated results and records the arguments of the last search."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        self._results = results
        self.search_kwargs: dict[str, Any] = {}

    def catalog(self) -> list[dict[str, Any]]:
        return [{"provider_name": "vivareal", "coverage_region": "Vale do Aço"}]

    async def federated_search(self, **kwargs: Any) -> dict[str, Any]:
        self.search_kwargs = kwargs
        providers = [{"provider": "vivareal", "status": "ok", "count": len(self._results), "error_code": None, "error": None}]
        return {"status": "ok", "providers": providers, "results": list(self._results)}

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        return {"photos": []}

    async def facets(self, provider: str) -> dict[str, Any]:
        return {}


def _client(service: LocatedService) -> TestClient:
    config = AppConfig(rate_limit_burst=1000, rate_limit_per_minute=100000)
    return TestClient(create_http_app(create_mcp_server(), config, service=service))


def _codes(response) -> list[str]:
    return [row["code"] for row in response.json()["results"]]


def test_locations_endpoint_lists_seeded_cities():
    with _client(LocatedService([])) as client:
        body = client.get("/api/locations").json()
    assert {entry["name"] for entry in body["cities"]} >= {"Timóteo", "Ipatinga"}
    assert body["neighborhoods"] == []


def test_search_annotates_city_neighborhood_and_transaction():
    service = LocatedService([_listing(1, "OLARIA, Timóteo / MG")])
    with _client(service) as client:
        row = client.get("/api/search").json()["results"][0]
    assert (row["city"], row["neighborhood"], row["transaction"]) == ("Timóteo", "Olaria", "rent")


def test_city_filter_keeps_listings_without_location_and_drops_other_cities():
    service = LocatedService(
        [
            _listing(1, "Centro, Timóteo"),
            _listing(2, "Centro, Ipatinga"),
            _listing(3, None),
        ]
    )
    with _client(service) as client:
        response = client.get("/api/search", params={"city": "timoteo"})
    assert service.search_kwargs["city"] == "Timóteo"
    assert _codes(response) == ["vivareal-1", "vivareal-3"]


def test_neighborhood_filter_excludes_and_counts_listings_without_neighborhood():
    service = LocatedService(
        [
            _listing(1, "Olaria, Timóteo"),
            _listing(2, "Centro, Timóteo"),
            _listing(3, "Timóteo"),
        ]
    )
    key = "timoteo/olaria"
    with _client(service) as client:
        body = client.get("/api/search", params={"city": "Timóteo", "neighborhoods": key}).json()
    assert [row["code"] for row in body["results"]] == ["vivareal-1"]
    assert body["hidden_without_neighborhood"] == 1


def test_filters_apply_before_the_page_cut():
    crowd = [_listing(index, "Centro, Ipatinga") for index in range(80)]
    matches = [_listing(100 + index, "Olaria, Timóteo") for index in range(3)]
    service = LocatedService(crowd + matches)
    with _client(service) as client:
        body = client.get(
            "/api/search", params={"city": "Timóteo", "neighborhoods": "timoteo/olaria", "limit": "5"}
        ).json()
    assert [row["code"] for row in body["results"]] == ["vivareal-100", "vivareal-101", "vivareal-102"]


def test_sale_transaction_is_rejected_until_supported():
    with _client(LocatedService([])) as client:
        response = client.get("/api/search", params={"transaction": "sale"})
    assert response.status_code == 400
