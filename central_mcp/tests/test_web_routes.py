"""Tests for the /api JSON routes and static UI mount, through the combined HTTP app."""

from typing import Any

import pytest
from starlette.testclient import TestClient

from central_mcp.config import AppConfig
from central_mcp.errors import ProviderError, ProviderErrorCode
from central_mcp.http_app import create_http_app
from central_mcp.server import create_mcp_server
from central_mcp.web.routes import FEDERATED_FETCH_LIMIT


class FakeService:
    """Stands in for RentalService so routes can be tested without subprocesses."""

    def __init__(self) -> None:
        self.search_kwargs: dict[str, Any] = {}
        self.facets_error: Exception | None = None
        self.detail_error: Exception | None = None

    def catalog(self) -> list[dict[str, Any]]:
        return [{"provider_name": "vivareal", "coverage_region": "Vale do Aço"}]

    async def federated_search(self, **kwargs: Any) -> dict[str, Any]:
        self.search_kwargs = kwargs
        projected = {
            "provider": "vivareal",
            "code": "123",
            "title": "Apto",
            "location": "Centro, Timóteo",
            "rent_price": 1500.0,
            "condo_fee": None,
            "iptu": None,
            "total_price": 1500.0,
            "bedrooms": 2,
            "url": "https://www.vivareal.com.br/imovel/123",
        }
        return {"status": "ok", "providers": [{"provider": "vivareal", "status": "ok"}], "results": [projected]}

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        if self.detail_error is not None:
            raise self.detail_error
        return {
            "title": "Apto",
            "url": "https://www.vivareal.com.br/imovel/123",
            "price": "R$ 1.500",
            "photos": ["https://cdn.test/1.jpg", "https://cdn.test/2.jpg"],
            "description": "Sol da manhã",
            "rent_price": 1500.0,
            "condo_fee": 200.0,
            "iptu": 0.0,
            "total_price": 1700.0,
        }

    async def facets(self, provider: str) -> dict[str, Any]:
        if self.facets_error is not None:
            raise self.facets_error
        return {"cities": [{"name": "Timóteo"}]}


def _client(service: FakeService, config: AppConfig | None = None) -> TestClient:
    cfg = config or AppConfig(rate_limit_burst=1000, rate_limit_per_minute=100000)
    app = create_http_app(create_mcp_server(), cfg, service=service)
    return TestClient(app)


def test_providers_endpoint_returns_catalog():
    with _client(FakeService()) as client:
        response = client.get("/api/providers")
    assert response.status_code == 200
    assert response.json()[0]["provider_name"] == "vivareal"


def test_search_passes_parsed_filters_and_returns_enriched_results():
    service = FakeService()
    with _client(service) as client:
        response = client.get(
            "/api/search",
            params={"city": "Timóteo", "bedrooms": "2", "max_price": "2000", "providers": "vivareal,helenaimoveis", "limit": "10"},
        )
    assert response.status_code == 200
    assert service.search_kwargs["providers"] == ["vivareal", "helenaimoveis"]
    assert service.search_kwargs["bedrooms"] == 2
    assert service.search_kwargs["max_price"] == 2000.0
    assert service.search_kwargs["include_raw"] is True
    assert service.search_kwargs["limit"] == FEDERATED_FETCH_LIMIT
    body = response.json()
    assert body["status"] == "ok"
    assert body["results"][0]["cover_photo"] == "https://cdn.test/1.jpg"
    assert body["results"][0]["official_url"] == "https://www.vivareal.com.br/imovel/123"


def test_search_without_filters_defaults_to_all_providers():
    service = FakeService()
    with _client(service) as client:
        client.get("/api/search")
    assert service.search_kwargs["providers"] is None
    assert service.search_kwargs["limit"] == FEDERATED_FETCH_LIMIT


@pytest.mark.parametrize(
    "params",
    [{"min_price": "abc"}, {"max_price": "nan"}, {"bedrooms": "dois"}, {"limit": "0"}, {"limit": "500"}, {"page": "0"}],
)
def test_search_rejects_invalid_numbers(params):
    with _client(FakeService()) as client:
        response = client.get("/api/search", params=params)
    assert response.status_code == 400
    assert "error" in response.json()


def test_search_maps_service_validation_error_to_400():
    class RejectingService(FakeService):
        async def federated_search(self, **kwargs: Any) -> dict[str, Any]:
            raise ValueError("Unknown provider: nope")

    with _client(RejectingService()) as client:
        response = client.get("/api/search", params={"providers": "nope"})
    assert response.status_code == 400
    assert "Unknown provider" in response.json()["error"]


def test_facets_requires_provider_query_param():
    with _client(FakeService()) as client:
        response = client.get("/api/facets")
    assert response.status_code == 400


def test_facets_unknown_provider_is_404():
    service = FakeService()
    service.facets_error = KeyError("nope")
    with _client(service) as client:
        response = client.get("/api/facets", params={"provider": "nope"})
    assert response.status_code == 404


def test_facets_returns_provider_payload():
    with _client(FakeService()) as client:
        response = client.get("/api/facets", params={"provider": "vivareal"})
    assert response.json() == {"cities": [{"name": "Timóteo"}]}


def test_listing_detail_returns_gallery_description_and_prices():
    with _client(FakeService()) as client:
        response = client.get("/api/listings/vivareal/123")
    assert response.status_code == 200
    body = response.json()
    assert body["photos"] == ["https://cdn.test/1.jpg", "https://cdn.test/2.jpg"]
    assert body["description"] == "Sol da manhã"
    assert body["total_price"] == 1700.0
    assert body["code"] == "123"


def test_listing_detail_provider_error_is_502():
    service = FakeService()
    service.detail_error = ProviderError("vivareal", ProviderErrorCode.TIMEOUT, "slow")
    with _client(service) as client:
        response = client.get("/api/listings/vivareal/123")
    assert response.status_code == 502
    assert response.json()["error_code"] == "timeout"


def test_mcp_endpoint_still_served_alongside_api():
    with _client(FakeService()) as client:
        response = client.post("/mcp", json={})
    assert response.status_code != 404


def test_web_disabled_removes_api_routes():
    cfg = AppConfig(rate_limit_burst=1000, rate_limit_per_minute=100000, web_enabled=False)
    with _client(FakeService(), cfg) as client:
        assert client.get("/api/providers").status_code == 404


def test_static_ui_served_from_configured_dir(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>Busca</title>", encoding="utf-8")
    cfg = AppConfig(rate_limit_burst=1000, rate_limit_per_minute=100000, static_dir=str(tmp_path))
    with _client(FakeService(), cfg) as client:
        page = client.get("/")
        api = client.get("/api/providers")
        health = client.get("/healthz")
    assert page.status_code == 200
    assert "Busca" in page.text
    assert api.status_code == 200
    assert health.json() == {"status": "healthy"}


def test_missing_static_dir_is_ignored(tmp_path):
    cfg = AppConfig(rate_limit_burst=1000, rate_limit_per_minute=100000, static_dir=str(tmp_path / "absent"))
    with _client(FakeService(), cfg) as client:
        assert client.get("/api/providers").status_code == 200
        assert client.get("/").status_code == 404


class CatalogWithImovelwebService(FakeService):
    """Catalog and federated results that include the unavailable imovelweb provider."""

    def catalog(self) -> list[dict[str, Any]]:
        return [
            {"provider_name": "vivareal", "coverage_region": "Vale do Aço"},
            {"provider_name": "imovelweb", "coverage_region": "Nacional"},
        ]

    async def federated_search(self, **kwargs: Any) -> dict[str, Any]:
        outcome = await super().federated_search(**kwargs)
        outcome["providers"] = [
            {"provider": "vivareal", "status": "ok", "count": 1, "error_code": None, "error": None},
            {
                "provider": "imovelweb",
                "status": "unavailable",
                "count": 0,
                "error_code": "unavailable",
                "error": "Browser required (Cloudflare/Patchright)",
            },
        ]
        outcome["status"] = "partial"
        return outcome


def test_providers_endpoint_hides_unavailable_providers():
    with _client(CatalogWithImovelwebService()) as client:
        response = client.get("/api/providers")
    names = [entry["provider_name"] for entry in response.json()]
    assert names == ["vivareal"]


def test_search_hides_unavailable_provider_outcomes_and_recomputes_status():
    with _client(CatalogWithImovelwebService()) as client:
        response = client.get("/api/search")
    body = response.json()
    assert [entry["provider"] for entry in body["providers"]] == ["vivareal"]
    assert body["status"] == "ok"
