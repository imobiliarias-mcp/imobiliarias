"""CLI entry point for Central Rental Research MCP server."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import uvicorn

from central_mcp.config import AppConfig
from central_mcp.http_app import create_http_app
from central_mcp.server import create_mcp_server


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(description="Central Rental Research MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http", "http"],
        default="stdio",
        help="Transport protocol (stdio, sse, streamable-http, http)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host address for HTTP/SSE transports")
    parser.add_argument("--port", type=int, default=8000, help="Port for HTTP/SSE transports")
    return parser


def _run_http(config: AppConfig, host: str, port: int) -> None:
    http_cfg = AppConfig(
        host=host,
        port=port,
        worker_timeout_seconds=config.worker_timeout_seconds,
        max_worker_stdout_bytes=config.max_worker_stdout_bytes,
        max_concurrent_workers=config.max_concurrent_workers,
        rate_limit_per_minute=config.rate_limit_per_minute,
        rate_limit_burst=config.rate_limit_burst,
        trusted_proxies=config.trusted_proxies,
        allowed_hosts=config.allowed_hosts,
        allowed_origins=config.allowed_origins,
        stateless_http=config.stateless_http,
        provider_min_interval_seconds=config.provider_min_interval_seconds,
    )
    server = create_mcp_server()
    app = create_http_app(server, http_cfg)
    uvicorn.run(app, host=host, port=port)


def run_server(transport: str, host: str, port: int) -> None:
    """Launch MCP server using the specified transport configuration."""
    config = AppConfig.from_env()
    if transport == "http":
        _run_http(config, host, port)
        return
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
