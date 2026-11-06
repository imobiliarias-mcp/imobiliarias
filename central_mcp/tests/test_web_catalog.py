"""Tests for the cached, thread-offloaded provider catalog used by /api/providers."""

import threading
import time
from typing import Any

from central_mcp.web.catalog import CachedCatalog


class _SlowCatalogService:
    """Blocking catalog like RentalService.catalog(), which spawns provider subprocesses."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay = delay_seconds
        self.calls = 0
        self.threads: list[threading.Thread] = []

    def catalog(self) -> list[dict[str, Any]]:
        self.calls += 1
        self.threads.append(threading.current_thread())
        time.sleep(self._delay)
        return [{"provider_name": "vivareal"}]


async def test_catalog_runs_off_the_event_loop_thread():
    service = _SlowCatalogService(delay_seconds=0)
    catalog = CachedCatalog(service, ttl_seconds=60)
    loop_thread = threading.current_thread()
    await catalog.providers()
    assert service.threads and service.threads[0] is not loop_thread


async def test_catalog_is_cached_between_requests():
    service = _SlowCatalogService(delay_seconds=0)
    catalog = CachedCatalog(service, ttl_seconds=60)
    first = await catalog.providers()
    second = await catalog.providers()
    assert first == second == [{"provider_name": "vivareal"}]
    assert service.calls == 1


async def test_concurrent_first_requests_build_catalog_once():
    service = _SlowCatalogService(delay_seconds=0.2)
    catalog = CachedCatalog(service, ttl_seconds=60)
    import asyncio

    results = await asyncio.gather(*(catalog.providers() for _ in range(5)))
    assert all(result == [{"provider_name": "vivareal"}] for result in results)
    assert service.calls == 1


async def test_zero_ttl_rebuilds_every_time():
    service = _SlowCatalogService(delay_seconds=0)
    catalog = CachedCatalog(service, ttl_seconds=0)
    await catalog.providers()
    await catalog.providers()
    assert service.calls == 2
