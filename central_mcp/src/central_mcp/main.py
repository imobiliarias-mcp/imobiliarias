"""CLI entry point for Central Rental Research MCP server."""

import argparse
import sys
from typing import Any

from central_mcp.server import create_mcp_server


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="Central Rental Research MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="Transport protocol (stdio, sse, streamable-http)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host address for HTTP/SSE transports")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP/SSE transports")
    return parser


def run_server(transport: str, host: str, port: int) -> None:
    """Launch MCP server using the specified transport configuration."""
    server = create_mcp_server()
    if transport == "stdio":
        server.run("stdio")
        return
    kwargs: dict[str, Any] = {"host": host, "port": port}
    server.run(transport, **kwargs)


def cli() -> None:
    """CLI runner invocation."""
    parser = create_parser()
    args = parser.parse_args()
    try:
        run_server(args.transport, args.host, args.port)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    cli()
