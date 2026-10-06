"""Unit tests for RentalService orchestration facade and federation contract."""

import pytest

from central_mcp.application.service import RentalService, project_listing
from central_mcp.errors import ProviderError, ProviderErrorCode
from central_mcp.providers.registry import ProviderRegistry


class MockAdapter:
    """Mock adapter simulating predictable provider response."""

    def __init__(self, name: str, should_fail: bool = False, error_code: ProviderErrorCode = ProviderErrorCode.UPSTREAM_ERROR) -> None:
        self._name = name
        self._should_fail = should_fail
        self._error_code = error_code

    def search_rentals(self, **kwargs):
        if self._should_fail:
            raise ProviderError(self._name, self._error_code, "Simulated failure")
        return {
            "provider": self._name,
            "total_count": 2,
            "listings": [
                {
                    "id": f"{self._name}-1",
                    "code": f"COD-{self._name}-1",
                    "title": f"Apto {self._name} 1",
                    "price": "R$ 1.200,00",
                    "bedrooms": 2,
                    "city": "Timóteo",
                    "neighborhood": "Centro",
                    "url": f"https://{self._name}.com/1",
                },
                {
                    "id": f"{self._name}-2",
                    "code": f"COD-{self._name}-2",
                    "title": f"Apto {self._name} 2",
                    "price": "R$ 1.500,00",
                    "bedrooms": 3,
                    "city": "Timóteo",
                    "url": f"https://{self._name}.com/2",
                },
            ],
        }

    def get_property_detail(self, property_code: str):
        return {"id": property_code, "title": f"Apto {self._name}", "rental_price": 1000.0}

    def get_facets(self):
        return {"cities": [{"name": "Timóteo"}]}

    def get_provider_info(self):
        return {"provider_name": self._name, "coverage_region": "Vale do Aço"}


def test_project_listing_compact_and_raw():
    raw_item = {
        "id": "123",
        "code": "C123",
        "title": "Apartamento Centro",
        "city": "Timóteo",
        "neighborhood": "Funcionários",
        "price": "R$ 1.000,00",
        "bedrooms": 2,
        "detail_url": "https://example.com/c123",
    }
    projected = project_listing("alecorretoramg", raw_item, include_raw=False)
    assert projected["provider"] == "alecorretoramg"
    assert projected["code"] == "C123"
    assert projected["title"] == "Apartamento Centro"
    assert projected["location"] == "Funcionários, Timóteo"
    assert projected["price"] == "R$ 1.000,00"
    assert projected["bedrooms"] == 2
    assert projected["url"] == "https://example.com/c123"
    assert "raw" not in projected

    projected_with_raw = project_listing("alecorretoramg", raw_item, include_raw=True)
    assert "raw" in projected_with_raw
    assert projected_with_raw["raw"] == raw_item


@pytest.mark.asyncio
async def test_service_federated_search_ok():
    registry = ProviderRegistry.create_default()
    registry.register("mock_a", MockAdapter("mock_a"))
    registry.register("mock_b", MockAdapter("mock_b"))
    service = RentalService(registry=registry)

    res = await service.federated_search(
        providers=["mock_a", "mock_b"],
        city="Timóteo",
        limit=10,
    )
    assert res["status"] == "ok"
    assert len(res["providers"]) == 2
    assert res["providers"][0]["status"] == "ok"
    assert res["providers"][0]["count"] == 2
    assert len(res["results"]) == 4


@pytest.mark.asyncio
async def test_service_federated_search_partial():
    registry = ProviderRegistry.create_default()
    registry.register("mock_a", MockAdapter("mock_a"))
    registry.register("mock_fail", MockAdapter("mock_fail", should_fail=True, error_code=ProviderErrorCode.TIMEOUT))
    service = RentalService(registry=registry)

    res = await service.federated_search(
        providers=["mock_a", "mock_fail"],
        city="Timóteo",
        limit=10,
    )
    assert res["status"] == "partial"
    assert len(res["results"]) == 2
    fail_summary = next(p for p in res["providers"] if p["provider"] == "mock_fail")
    assert fail_summary["status"] == "error"
    assert fail_summary["error_code"] == "timeout"
    assert "Simulated failure" in fail_summary["error"]


@pytest.mark.asyncio
async def test_service_federated_search_all_error():
    registry = ProviderRegistry.create_default()
    registry.register("mock_1", MockAdapter("mock_1", should_fail=True))
    registry.register("mock_2", MockAdapter("mock_2", should_fail=True))
    service = RentalService(registry=registry)

    res = await service.federated_search(
        providers=["mock_1", "mock_2"],
        city="Timóteo",
    )
    assert res["status"] == "error"
    assert len(res["results"]) == 0


@pytest.mark.asyncio
async def test_service_limit_caps_results():
    registry = ProviderRegistry.create_default()
    registry.register("mock_a", MockAdapter("mock_a"))
    registry.register("mock_b", MockAdapter("mock_b"))
    service = RentalService(registry=registry)

    res = await service.federated_search(
        providers=["mock_a", "mock_b"],
        limit=3,
    )
    assert len(res["results"]) == 3


@pytest.mark.asyncio
async def test_service_unsupported_filter_raises_error():
    registry = ProviderRegistry.create_default()
    service = RentalService(registry=registry)

    with pytest.raises(ProviderError) as exc_info:
        await service.search(
            provider="imovelweb",
            max_price=1000.0,
        )
    assert exc_info.value.code == ProviderErrorCode.UNSUPPORTED_FILTER
