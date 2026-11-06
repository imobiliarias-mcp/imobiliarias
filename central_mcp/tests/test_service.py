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


@pytest.mark.asyncio
async def test_service_detail_rejects_ssrf_urls():
    registry = ProviderRegistry.create_default()
    registry.register("vivareal", MockAdapter("vivareal"))
    service = RentalService(registry=registry)

    with pytest.raises(ValueError, match="Property code cannot be a URL"):
        await service.detail(provider="vivareal", property_code="http://127.0.0.1:8000/internal")

    with pytest.raises(ValueError, match="Property code contains invalid characters"):
        await service.detail(provider="vivareal", property_code="code with spaces")


def test_project_listing_with_condo_and_total_price():
    raw_item = {
        "id": "123",
        "code": "C123",
        "title": "Apartamento Centro",
        "city": "Timóteo",
        "neighborhood": "Funcionários",
        "price": "R$ 1.200,00",
        "condo_fee": "R$ 300,00",
        "bedrooms": 2,
        "detail_url": "https://example.com/c123",
    }
    projected = project_listing("vivareal", raw_item)
    assert projected["rent_price"] == 1200.0
    assert projected["condo_fee"] == 300.0
    assert projected["total_price"] == 1500.0
    assert projected["price"] == "R$ 1.200,00"


def test_project_listing_without_condo_fee():
    raw_item = {
        "id": "124",
        "code": "C124",
        "title": "Casa Bairro",
        "city": "Timóteo",
        "price": 1000.0,
        "bedrooms": 3,
        "detail_url": "https://example.com/c124",
    }
    projected = project_listing("casalinhares", raw_item)
    assert projected["rent_price"] == 1000.0
    assert projected["condo_fee"] is None
    assert projected["total_price"] == 1000.0


@pytest.mark.asyncio
async def test_service_detail_includes_condo_breakdown():
    class DetailMockAdapter(MockAdapter):
        def get_property_detail(self, property_code: str):
            return {
                "id": property_code,
                "title": "Apto Luxo",
                "price": "R$ 2.000,00",
                "condominio": "R$ 450,00",
            }

    registry = ProviderRegistry.create_default()
    registry.register("mock_detail", DetailMockAdapter("mock_detail"))
    service = RentalService(registry=registry)

    detail = await service.detail("mock_detail", "APT-99")
    assert detail["rent_price"] == 2000.0
    assert detail["condo_fee"] == 450.0
    assert detail["total_price"] == 2450.0


def test_project_listing_with_condo_and_iptu():
    raw_item = {
        "id": "125",
        "code": "C125",
        "title": "Apartamento Luxo",
        "city": "Timóteo",
        "price": "R$ 1.200,00",
        "condo_fee": "R$ 300,00",
        "iptu": "R$ 100,00",
        "bedrooms": 2,
    }
    projected = project_listing("vivareal", raw_item)
    assert projected["rent_price"] == 1200.0
    assert projected["condo_fee"] == 300.0
    assert projected["iptu"] == 100.0
    assert projected["total_price"] == 1600.0


def test_project_listing_with_iptu_only():
    raw_item = {
        "id": "126",
        "code": "C126",
        "title": "Casa Bairro",
        "city": "Timóteo",
        "price": 1000.0,
        "iptu": 50.0,
        "bedrooms": 3,
    }
    projected = project_listing("casalinhares", raw_item)
    assert projected["rent_price"] == 1000.0
    assert projected["condo_fee"] is None
    assert projected["iptu"] == 50.0
    assert projected["total_price"] == 1050.0


@pytest.mark.asyncio
async def test_service_detail_includes_iptu_and_total_price():
    class DetailWithIptuMockAdapter(MockAdapter):
        def get_property_detail(self, property_code: str):
            return {
                "id": property_code,
                "title": "Apto Centro",
                "price": "R$ 2.000,00",
                "condominio": "R$ 450,00",
                "valoriptu": "R$ 150,00",
            }

    registry = ProviderRegistry.create_default()
    registry.register("mock_iptu_detail", DetailWithIptuMockAdapter("mock_iptu_detail"))
    service = RentalService(registry=registry)

    detail = await service.detail("mock_iptu_detail", "APT-100")
    assert detail["rent_price"] == 2000.0
    assert detail["condo_fee"] == 450.0
    assert detail["iptu"] == 150.0
    assert detail["total_price"] == 2600.0





class CityRecordingAdapter:
    """Adapter that records the city it was asked to search."""

    def __init__(self) -> None:
        self.cities: list[str] = []

    def search_rentals(self, **kwargs):
        self.cities.append(kwargs["city"])
        return {"listings": []}


async def test_federated_search_applies_default_city_for_city_required_provider():
    adapter = CityRecordingAdapter()
    registry = ProviderRegistry.create_default()
    registry.register("epifanioimoveis", adapter)
    service = RentalService(registry=registry)

    await service.federated_search(providers=["epifanioimoveis"])
    assert adapter.cities == ["Timóteo"]


async def test_search_applies_default_city_when_city_missing():
    adapter = CityRecordingAdapter()
    registry = ProviderRegistry.create_default()
    registry.register("niltoncorretordeimoveis", adapter)
    service = RentalService(registry=registry)

    await service.search("niltoncorretordeimoveis")
    assert adapter.cities == ["Timóteo"]


async def test_search_keeps_explicit_city_for_city_required_provider():
    adapter = CityRecordingAdapter()
    registry = ProviderRegistry.create_default()
    registry.register("epifanioimoveis", adapter)
    service = RentalService(registry=registry)

    await service.search("epifanioimoveis", city="Ipatinga")
    assert adapter.cities == ["Ipatinga"]


async def test_federated_search_without_default_keeps_empty_city_for_other_providers():
    adapter = CityRecordingAdapter()
    registry = ProviderRegistry.create_default()
    registry.register("vivareal", adapter)
    service = RentalService(registry=registry)

    await service.federated_search(providers=["vivareal"])
    assert adapter.cities == [""]
