"""Combined Starlette application supporting streamable HTTP, SSE, and health checks."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from central_mcp.application.service import RentalService
from central_mcp.config import AppConfig
from central_mcp.limits import InFlightLimiter, TokenBucketLimiter
from central_mcp.web.routes import build_static_mount, build_web_routes

logger = logging.getLogger(__name__)


class RateLimitMiddleware:
    """ASGI middleware applying token-bucket and in-flight request limits."""

    def __init__(self, app: ASGIApp, config: AppConfig) -> None:
        self._app = app
        self._config = config
        self._bucket = TokenBucketLimiter(
            rate_per_minute=config.rate_limit_per_minute,
            burst=config.rate_limit_burst,
        )
        self._in_flight = InFlightLimiter(max_in_flight=config.max_in_flight_requests)

    def _extract_client_ip(self, scope: Scope) -> str:
        client = scope.get("client")
        host = client[0] if client else "127.0.0.1"
        if host in self._config.trusted_proxies:
            headers = Headers(scope=scope)
            xff = headers.get("x-forwarded-for")
            if xff:
                return xff.split(",")[0].strip()
        return host

    async def _send_rejection(self, send: Send, status: int, body: dict[str, Any], headers: dict[str, str]) -> None:
        payload = json.dumps(body).encode("utf-8")
        raw_headers = [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()]
        raw_headers.append((b"content-type", b"application/json"))
        await send({"type": "http.response.start", "status": status, "headers": raw_headers})
        await send({"type": "http.response.body", "body": payload})

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/healthz":
            await self._app(scope, receive, send)
            return
        if not self._in_flight.try_acquire():
            await self._send_rejection(send, 503, {"error": "Server busy"}, {})
            return
        try:
            client_ip = self._extract_client_ip(scope)
            allowed, retry_after = self._bucket.check_and_consume(client_ip)
            if not allowed:
                headers = {"Retry-After": str(int(retry_after))}
                await self._send_rejection(send, 429, {"error": "Rate limit exceeded"}, headers)
                return
            await self._app(scope, receive, send)
        finally:
            self._in_flight.release()


async def healthz_endpoint(request: Any) -> JSONResponse:
    """Readiness/health check probe."""
    return JSONResponse({"status": "healthy"})


def create_http_app(
    server: MCPServer,
    config: AppConfig,
    service: RentalService | None = None,
) -> ASGIApp:
    """Combine MCP, health, JSON API and static UI routes into a single Starlette app.

    The static UI mount is added last so it cannot shadow the MCP or API routes.
    """
    enable_dns = "*" not in config.allowed_hosts
    hosts = [h for h in config.allowed_hosts if h != "*"]
    if "testserver" not in hosts:
        hosts.append("testserver")
    origins = [o for o in config.allowed_origins if o != "*"]
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=enable_dns,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )
    st_app = server.streamable_http_app(
        stateless_http=config.stateless_http,
        transport_security=security,
        host=config.host,
    )
    sse_app = server.sse_app(
        transport_security=security,
        host=config.host,
    )
    routes = [Route("/healthz", healthz_endpoint)]
    routes.extend(st_app.routes)
    routes.extend(sse_app.routes)
    warm_up: Callable[[], Awaitable[None]] | None = None
    if config.web_enabled:
        surface = build_web_routes(service or RentalService(), config)
        routes.extend(surface.routes)
        warm_up = surface.warm_up
        static_mount = build_static_mount(config.static_dir)
        if static_mount is not None:
            routes.append(static_mount)
    lifespan = _with_background_warm_up(st_app.router.lifespan_context, warm_up)
    base_app = Starlette(routes=routes, lifespan=lifespan)
    return RateLimitMiddleware(base_app, config)


def _with_background_warm_up(
    base_lifespan: Callable[[Any], Any],
    warm_up: Callable[[], Awaitable[None]] | None,
) -> Callable[[Any], Any]:
    """Run warm_up as a background task for the app's lifetime, without delaying startup."""

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        async with base_lifespan(app):
            task = _start_warm_up(warm_up)
            try:
                yield
            finally:
                if task is not None:
                    task.cancel()

    return lifespan


def _start_warm_up(warm_up: Callable[[], Awaitable[None]] | None) -> asyncio.Task[None] | None:
    if warm_up is None:
        return None
    return asyncio.create_task(_run_warm_up(warm_up))


async def _run_warm_up(warm_up: Callable[[], Awaitable[None]]) -> None:
    try:
        await warm_up()
    except Exception:
        logger.exception("background warm-up failed; data will be built on first request")
