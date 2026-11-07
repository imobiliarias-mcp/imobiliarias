"""Tests for the shared outcome cache: TTL reuse, single-flight fan-out, and what is never stored."""

import asyncio
from typing import Any

import pytest

from central_mcp.web.search_cache import SearchOutcomeCache


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class CountingFetch:
    """Records calls and returns an outcome; can be gated so calls overlap."""

    def __init__(self, outcome: dict[str, Any] | None = None) -> None:
        self.calls = 0
        self.outcome = outcome if outcome is not None else {"status": "ok", "results": [1]}
        self.gate: asyncio.Event | None = None

    async def __call__(self) -> dict[str, Any]:
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        return self.outcome


def _cache(ttl: float = 600.0, max_entries: int = 6, clock: FakeClock | None = None) -> SearchOutcomeCache:
    return SearchOutcomeCache(ttl_seconds=ttl, max_entries=max_entries, clock=clock or FakeClock())


async def test_second_call_within_ttl_reuses_the_outcome():
    cache, fetch = _cache(), CountingFetch()
    first = await cache.get_or_fetch(("k",), fetch)
    second = await cache.get_or_fetch(("k",), fetch)
    assert first == second
    assert fetch.calls == 1


async def test_entry_expires_after_ttl():
    clock = FakeClock()
    cache, fetch = _cache(ttl=60.0, clock=clock), CountingFetch()
    await cache.get_or_fetch(("k",), fetch)
    clock.now = 61.0
    await cache.get_or_fetch(("k",), fetch)
    assert fetch.calls == 2


async def test_different_keys_fetch_separately():
    cache, fetch = _cache(), CountingFetch()
    await cache.get_or_fetch(("a",), fetch)
    await cache.get_or_fetch(("b",), fetch)
    assert fetch.calls == 2


async def test_concurrent_callers_share_one_fetch():
    cache, fetch = _cache(), CountingFetch()
    fetch.gate = asyncio.Event()
    waiters = [asyncio.create_task(cache.get_or_fetch(("k",), fetch)) for _ in range(5)]
    await asyncio.sleep(0)
    fetch.gate.set()
    results = await asyncio.gather(*waiters)
    assert fetch.calls == 1
    assert all(result == fetch.outcome for result in results)


async def test_zero_ttl_still_shares_concurrent_fetches_but_stores_nothing():
    cache, fetch = _cache(ttl=0.0), CountingFetch()
    fetch.gate = asyncio.Event()
    waiters = [asyncio.create_task(cache.get_or_fetch(("k",), fetch)) for _ in range(3)]
    await asyncio.sleep(0)
    fetch.gate.set()
    await asyncio.gather(*waiters)
    assert fetch.calls == 1
    await cache.get_or_fetch(("k",), fetch)
    assert fetch.calls == 2


async def test_failed_fetch_propagates_and_is_not_cached():
    cache = _cache()
    calls = 0

    async def failing() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise ValueError("Unknown provider: nope")

    with pytest.raises(ValueError, match="Unknown provider"):
        await cache.get_or_fetch(("k",), failing)
    with pytest.raises(ValueError):
        await cache.get_or_fetch(("k",), failing)
    assert calls == 2


async def test_error_status_outcome_is_not_cached():
    cache = _cache()
    fetch = CountingFetch(outcome={"status": "error", "results": []})
    await cache.get_or_fetch(("k",), fetch)
    await cache.get_or_fetch(("k",), fetch)
    assert fetch.calls == 2


async def test_partial_outcome_is_cached():
    cache = _cache()
    fetch = CountingFetch(outcome={"status": "partial", "results": [1]})
    await cache.get_or_fetch(("k",), fetch)
    await cache.get_or_fetch(("k",), fetch)
    assert fetch.calls == 1


async def test_refresh_bypasses_the_cached_entry_and_replaces_it():
    cache, fetch = _cache(), CountingFetch()
    await cache.get_or_fetch(("k",), fetch)
    fetch.outcome = {"status": "ok", "results": [2]}
    refreshed = await cache.get_or_fetch(("k",), fetch, refresh=True)
    assert refreshed == {"status": "ok", "results": [2]}
    assert fetch.calls == 2
    assert await cache.get_or_fetch(("k",), fetch) == {"status": "ok", "results": [2]}
    assert fetch.calls == 2


async def test_bounded_entries_evict_the_oldest_key():
    clock = FakeClock()
    cache = _cache(max_entries=2, clock=clock)
    fetch = CountingFetch()
    for key in ("a", "b", "c"):
        clock.now += 1.0
        await cache.get_or_fetch((key,), fetch)
    await cache.get_or_fetch(("a",), fetch)
    assert fetch.calls == 4


async def test_cancelled_first_caller_does_not_cancel_the_shared_fetch():
    cache, fetch = _cache(), CountingFetch()
    fetch.gate = asyncio.Event()
    first = asyncio.create_task(cache.get_or_fetch(("k",), fetch))
    second = asyncio.create_task(cache.get_or_fetch(("k",), fetch))
    await asyncio.sleep(0)
    first.cancel()
    fetch.gate.set()
    assert await second == fetch.outcome
    assert fetch.calls == 1
    await cache.get_or_fetch(("k",), fetch)
    assert fetch.calls == 1
