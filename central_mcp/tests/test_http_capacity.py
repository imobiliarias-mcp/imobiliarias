"""Tests that HTTP in-flight capacity is independent of the provider worker setting."""

import asyncio
from typing import Any

from central_mcp.config import AppConfig
from central_mcp.http_app import RateLimitMiddleware


def _scope(path: str = "/api/search") -> dict[str, Any]:
    return {"type": "http", "path": path, "client": ("203.0.113.7", 4321), "headers": []}


async def _no_body_receive() -> dict[str, Any]:
    return {"type": "http.request", "body": b"", "more_body": False}


def test_in_flight_capacity_comes_from_request_setting_not_worker_count():
    assert AppConfig(max_concurrent_workers=1, max_in_flight_requests=16).max_in_flight_requests == 16


def test_config_rejects_non_positive_in_flight_capacity():
    import pytest

    with pytest.raises(ValueError, match="max_in_flight_requests"):
        AppConfig.from_env({"CENTRAL_MCP_MAX_IN_FLIGHT_REQUESTS": "0"})


async def test_concurrent_requests_up_to_capacity_are_served_and_extra_get_503():
    gate = asyncio.Event()

    async def slow_app(scope, receive, send):
        await gate.wait()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    config = AppConfig(
        max_concurrent_workers=1,
        max_in_flight_requests=3,
        rate_limit_burst=1000,
        rate_limit_per_minute=1_000_000,
    )
    middleware = RateLimitMiddleware(slow_app, config)
    statuses: list[int] = []

    async def collecting_send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    tasks = [asyncio.create_task(middleware(_scope(), _no_body_receive, collecting_send)) for _ in range(4)]
    await asyncio.sleep(0.05)
    gate.set()
    await asyncio.gather(*tasks)
    assert sorted(statuses) == [200, 200, 200, 503]
