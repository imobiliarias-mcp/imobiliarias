"""Unit tests for RentalService orchestration facade."""

import pytest

from central_mcp.application.service import RentalService
from central_mcp.providers.registry import ProviderRegistry


class MockAdapter:
    """Mock adapter simulating predictable provider response."""

    def __init__(self, name: str) -> None:
        self._name = name

    def search_rentals(self, **kwargs):
        return {
            "provider": self._name,
            "total_count": 1,
            "listings": [
                {
                    "id": f"{self._name}-1",
                    "title": f"Apto {self._name}",
                    "rental_price": 1000.0,
                    "rental_price_formatted": "R$ 1.000,00",
                    "url": f"https://{self._name}.com/1",
                }
            ],
        }

    def get_property_detail(self, property_code: str):
        return {"id": property_code, "title": f"Apto {self._name}", "rental_price": 1000.0}

    def get_facets(self):
        return {"cities": [{"name": "Timóteo"}]}

    def get_provider_info(self):
        return {"provider_name": self._name, "coverage_region": "Vale do Aço"}


@pytest.mark.asyncio
async def test_service_single_search():
    """Verify service delegates single search to registry."""
    registry = ProviderRegistry.create_default()
    registry.register("mock_a", MockAdapter("mock_a"))
    service = RentalService(registry=registry)

    result = await service.search(provider="mock_a", city="Timóteo", bedrooms=2)
    assert result["provider"] == "mock_a"
    assert len(result["listings"]) == 1


@pytest.mark.asyncio
async def test_service_federated_search():
    """Verify service aggregates multiple providers in federated search."""
    registry = ProviderRegistry.create_default()
    registry.register("mock_a", MockAdapter("mock_a"))
    registry.register("mock_b", MockAdapter("mock_b"))
    service = RentalService(registry=registry)

    result = await service.federated_search(
        providers=["mock_a", "mock_b"],
        city="Timóteo",
        bedrooms=2,
    )
    assert result["total_results"] == 2
    assert len(result["results"]) == 2


@pytest.mark.asyncio
async def test_service_detail():
    """Verify service delegates detail retrieval."""
    registry = ProviderRegistry.create_default()
    registry.register("mock_a", MockAdapter("mock_a"))
    service = RentalService(registry=registry)

    detail = await service.detail(provider="mock_a", property_code="101")
    assert detail["id"] == "101"


@pytest.mark.asyncio
async def test_service_facets():
    """Verify service delegates facet retrieval."""
    registry = ProviderRegistry.create_default()
    registry.register("mock_a", MockAdapter("mock_a"))
    service = RentalService(registry=registry)

    facets = await service.facets(provider="mock_a")
    assert "cities" in facets
