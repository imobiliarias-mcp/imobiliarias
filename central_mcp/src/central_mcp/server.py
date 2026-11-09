"""Central Rental Research Model Context Protocol (MCP) server."""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from central_mcp.application.service import RentalService


def create_mcp_server(service: RentalService | None = None) -> MCPServer:
    """Create and configure the central MCP server with registered rental research tools."""
    app_service = service or RentalService()
    server = MCPServer(name="Central Rental Research MCP", version="0.2.0")
    _register_catalog_tool(server, app_service)
    _register_search_tools(server, app_service)
    _register_detail_and_facets_tools(server, app_service)
    return server


def _register_catalog_tool(server: MCPServer, service: RentalService) -> None:
    """Register list_rental_providers catalog tool."""

    @server.tool(
        name="list_rental_providers",
        description="List all 16 integrated real estate agencies and portals, coverage regions, and capabilities.",
    )
    async def list_rental_providers() -> list[dict[str, Any]]:
        return service.catalog()


def _register_search_tools(server: MCPServer, service: RentalService) -> None:
    """Register single and federated search tools."""

    @server.tool(
        name="search_rentals",
        description="Search rental properties on a specific agency or portal with optional criteria.",
    )
    async def search_rentals(
        provider: str,
        city: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        page: int = 1,
        include_raw: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await service.search(
            provider=provider,
            city=city,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            property_type=property_type,
            page=page,
            include_raw=include_raw,
            limit=limit,
        )

    @server.tool(
        name="federated_search_rentals",
        description="Federated parallel search for rental properties across multiple agencies (or all available).",
    )
    async def federated_search_rentals(
        providers: list[str] | None = None,
        city: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        bedrooms: int | None = None,
        property_type: str | None = None,
        page: int = 1,
        include_raw: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        return await service.federated_search(
            providers=providers,
            city=city,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            property_type=property_type,
            page=page,
            include_raw=include_raw,
            limit=limit,
        )


def _register_detail_and_facets_tools(server: MCPServer, service: RentalService) -> None:
    """Register property detail and taxonomy facets tools."""

    @server.tool(
        name="get_rental_detail",
        description="Get complete property specifications, features, and photo gallery for a property code.",
    )
    async def get_rental_detail(provider: str, property_code: str) -> dict[str, Any]:
        return await service.detail(provider=provider, property_code=property_code)

    @server.tool(
        name="get_rental_facets",
        description="Get search facets (available cities, neighborhoods, property types) for a provider.",
    )
    async def get_rental_facets(provider: str) -> dict[str, Any]:
        return await service.facets(provider=provider)
