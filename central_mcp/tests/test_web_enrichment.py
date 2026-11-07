"""Tests for enriching search results with detail media, isolating per-item failures."""

import asyncio
import time

from central_mcp.errors import ProviderError, ProviderErrorCode
from central_mcp.web.cache import TtlCache
from central_mcp.web.enrichment import ListingEnricher


class _FakeService:
    def __init__(self, details: dict[tuple[str, str], dict | Exception]) -> None:
        self._details = details
        self.calls: list[tuple[str, str]] = []

    async def detail(self, provider: str, property_code: str) -> dict:
        self.calls.append((provider, property_code))
        outcome = self._details[(provider, property_code)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _item(provider: str, code: str | None, url: str = "https://site.test/x") -> dict:
    return {"provider": provider, "code": code, "title": "Apto", "url": url, "total_price": 1000.0}


async def test_enrich_attaches_photos_and_description_from_detail():
    service = _FakeService({("vivareal", "1"): {"photos": ["https://cdn.test/1.jpg"], "description": "Bonito"}})
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=2)
    [listing] = await enricher.enrich([_item("vivareal", "1")])
    assert listing.photos == ("https://cdn.test/1.jpg",)
    assert listing.description == "Bonito"


async def test_enrich_keeps_item_when_detail_fails():
    service = _FakeService({("vivareal", "1"): ProviderError("vivareal", ProviderErrorCode.TIMEOUT, "slow")})
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=2)
    [listing] = await enricher.enrich([_item("vivareal", "1")])
    assert listing.photos == ()
    assert listing.official_url == "https://site.test/x"


async def test_enrich_skips_detail_when_code_missing():
    service = _FakeService({})
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=2)
    [listing] = await enricher.enrich([_item("novaimobiliaria", None)])
    assert listing.photos == ()
    assert service.calls == []


async def test_enrich_empty_list_returns_empty():
    enricher = ListingEnricher(_FakeService({}), TtlCache(ttl_seconds=60), concurrency=2)
    assert await enricher.enrich([]) == []


async def test_enrich_one_failure_does_not_affect_others():
    service = _FakeService(
        {
            ("a", "1"): {"photos": ["https://cdn.test/a.jpg"]},
            ("b", "2"): RuntimeError("boom"),
            ("c", "3"): {"description": "ok"},
        }
    )
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=3)
    listings = await enricher.enrich([_item("a", "1"), _item("b", "2"), _item("c", "3")])
    assert [item.photos for item in listings] == [("https://cdn.test/a.jpg",), (), ()]
    assert listings[2].description == "ok"


async def test_enrich_uses_cache_for_repeated_details():
    service = _FakeService({("vivareal", "1"): {"photos": ["https://cdn.test/1.jpg"]}})
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=2)
    await enricher.enrich([_item("vivareal", "1")])
    [listing] = await enricher.enrich([_item("vivareal", "1")])
    assert service.calls == [("vivareal", "1")]
    assert listing.photos == ("https://cdn.test/1.jpg",)


async def test_failed_detail_is_not_cached():
    service = _FakeService({("vivareal", "1"): RuntimeError("down")})
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=2)
    await enricher.enrich([_item("vivareal", "1")])
    await enricher.enrich([_item("vivareal", "1")])
    assert len(service.calls) == 2


class _SlowService:
    """Detail source where some listings take far longer than the enrichment budget."""

    def __init__(self, delays: dict[str, float]) -> None:
        self._delays = delays

    async def detail(self, provider: str, property_code: str) -> dict:
        await asyncio.sleep(self._delays[property_code])
        return {"photos": [f"https://cdn.test/{property_code}.jpg"]}


async def test_enrich_returns_within_budget_without_waiting_for_slow_details():
    service = _SlowService({"fast": 0.0, "slow": 30.0})
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=2, budget_seconds=0.2)
    started = time.monotonic()
    fast, slow = await enricher.enrich([_item("a", "fast"), _item("a", "slow")])
    assert time.monotonic() - started < 2.0
    assert fast.photos == ("https://cdn.test/fast.jpg",)
    assert slow.photos == ()
    assert slow.official_url == "https://site.test/x"


async def test_enrich_keeps_details_finished_before_budget_expires():
    service = _SlowService({"a": 0.0, "b": 0.0})
    enricher = ListingEnricher(service, TtlCache(ttl_seconds=60), concurrency=2, budget_seconds=5.0)
    listings = await enricher.enrich([_item("p", "a"), _item("p", "b")])
    assert [item.photos for item in listings] == [("https://cdn.test/a.jpg",), ("https://cdn.test/b.jpg",)]
