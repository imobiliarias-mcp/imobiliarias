"""Tests that the provider catalog is built in the background at startup, not on the first request."""

import time
from typing import Any

from starlette.testclient import TestClient

from central_mcp.config import AppConfig
from central_mcp.http_app import create_http_app
from central_mcp.server import create_mcp_server
from central_mcp.web.catalog import CachedCatalog


class _CountingCatalogSource:
    def __init__(self) -> None:
        self.calls = 0

    def catalog(self) -> list[dict[str, Any]]:
        self.calls += 1
        return [{"provider_name": "vivareal"}]


async def test_warm_up_builds_catalog_once_and_later_reads_use_cache():
    source = _CountingCatalogSource()
    catalog = CachedCatalog(source, ttl_seconds=60)
    await catalog.warm_up()
    assert await catalog.providers() == [{"provider_name": "vivareal"}]
    assert source.calls == 1


def test_startup_warms_catalog_so_first_request_does_not_rebuild_it():
    source = _CountingCatalogSource()

    class _Service:
        def __init__(self) -> None:
            self.catalog = source.catalog

    config = AppConfig(rate_limit_burst=1000, rate_limit_per_minute=100000)
    app = create_http_app(create_mcp_server(), config, service=_Service())
    with TestClient(app) as client:
        deadline = time.monotonic() + 5
        while source.calls == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        assert source.calls == 1
        response = client.get("/api/providers")
    assert response.status_code == 200
    assert source.calls == 1
