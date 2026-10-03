"""Central Rental Research Model Context Protocol (MCP) server."""

from typing import Any

from mcp.server.mcpserver import MCPServer

from central_mcp.application.service import RentalService


def create_mcp_server(service: RentalService | None = None) -> MCPServer:
    """Create and configure the central MCP server with registered rental research tools."""
    app_service = service or RentalService()
    server = MCPServer(name="Central Rental Research MCP", version="0.1.0")
    _register_catalog_tool(server, app_service)
    _register_search_tools(server, app_service)
    _register_detail_and_facets_tools(server, app_service)
    return server


def _register_catalog_tool(server: MCPServer, service: RentalService) -> None:
    """Register list_rental_providers catalog tool."""

    @server.tool(
        name="list_rental_providers",
        description="Lista as 15 imobiliárias e portais integrados, regiões atendidas e operações suportadas.",
    )
    async def list_rental_providers() -> list[dict[str, Any]]:
        return service.catalog()


def _register_search_tools(server: MCPServer, service: RentalService) -> None:
    """Register single and federated search tools."""

    @server.tool(
        name="search_rentals",
        description="Pesquisa imóveis para alugar em uma imobiliária específica do Vale do Aço ou portal nacional.",
    )
    async def search_rentals(
        provider: str,
        city: str = "Timóteo",
        min_price: float = 0.0,
        max_price: float = 0.0,
        bedrooms: int = 0,
        property_type: str = "",
        page: int = 1,
    ) -> dict[str, Any]:
        return await service.search(
            provider=provider,
            city=city,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            property_type=property_type,
            page=page,
        )

    @server.tool(
        name="federated_search_rentals",
        description="Pesquisa simultânea e federada de aluguéis em múltiplas imobiliárias (ou em todas).",
    )
    async def federated_search_rentals(
        providers: list[str] | None = None,
        city: str = "Timóteo",
        min_price: float = 0.0,
        max_price: float = 0.0,
        bedrooms: int = 0,
        property_type: str = "",
        page: int = 1,
    ) -> dict[str, Any]:
        return await service.federated_search(
            providers=providers,
            city=city,
            min_price=min_price,
            max_price=max_price,
            bedrooms=bedrooms,
            property_type=property_type,
            page=page,
        )


def _register_detail_and_facets_tools(server: MCPServer, service: RentalService) -> None:
    """Register property detail and taxonomy facets tools."""

    @server.tool(
        name="get_rental_detail",
        description="Obtém detalhes completos, especificações e fotos de um imóvel em uma imobiliária.",
    )
    async def get_rental_detail(provider: str, property_code: str) -> dict[str, Any]:
        return await service.detail(provider=provider, property_code=property_code)

    @server.tool(
        name="get_rental_facets",
        description="Obtém cidades, bairros e categorias disponíveis em uma imobiliária.",
    )
    async def get_rental_facets(provider: str) -> dict[str, Any]:
        return await service.facets(provider=provider)
