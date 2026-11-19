"""Unit tests for Central MCP server creation and tool execution."""

import pytest

from central_mcp.application.service import RentalService
from central_mcp.providers.registry import ProviderRegistry
from central_mcp.server import create_mcp_server


class StubAdapter:
    """Stub adapter for testing tools."""

    def search_rentals(self, **kwargs):
        return {
            "provider": "cabralporto",
            "total_count": 1,
            "listings": [{"id": "1", "title": "Casa Timóteo", "rental_price": 950.0}],
        }

    def get_property_detail(self, property_code: str):
        return {"id": property_code, "title": "Casa Timóteo", "price": "R$ 950,00"}

    def get_facets(self):
        return {"cities": [{"name": "Timóteo"}]}

    def get_provider_info(self):
        return {"provider_name": "cabralporto", "coverage_region": "Vale do Aço"}


@pytest.mark.asyncio
async def test_mcp_server_lists_tools():
    """Verify MCP server registers core rental research tools."""
    registry = ProviderRegistry.create_default()
    registry.register("cabralporto", StubAdapter())
    service = RentalService(registry=registry)
    server = create_mcp_server(service=service)

    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "list_rental_providers" in tool_names
    assert "search_rentals" in tool_names
    assert "federated_search_rentals" in tool_names
    assert "get_rental_detail" in tool_names
    assert "get_rental_facets" in tool_names


@pytest.mark.asyncio
async def test_mcp_server_call_list_providers():
    """Verify list_rental_providers tool execution."""
    registry = ProviderRegistry.create_default()
    registry.register("cabralporto", StubAdapter())
    service = RentalService(registry=registry)
    server = create_mcp_server(service=service)

    result = await server.call_tool("list_rental_providers", {})
    assert result is not None


@pytest.mark.asyncio
async def test_mcp_server_call_search():
    """Verify search_rentals tool execution."""
    registry = ProviderRegistry.create_default()
    registry.register("cabralporto", StubAdapter())
    service = RentalService(registry=registry)
    server = create_mcp_server(service=service)

    result = await server.call_tool("search_rentals", {"provider": "cabralporto", "city": "Timóteo"})
    assert result is not None
