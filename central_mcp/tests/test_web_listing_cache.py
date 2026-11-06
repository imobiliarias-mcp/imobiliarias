"""Tests for the web listing DTO and the TTL detail cache."""

from central_mcp.web.cache import TtlCache
from central_mcp.web.listing import WebListing


def test_listing_from_search_and_detail_merges_media():
    projected = {
        "provider": "vivareal",
        "code": "123",
        "title": "Apto 2 quartos",
        "location": "Centro, Timóteo",
        "rent_price": 1500.0,
        "condo_fee": 300.0,
        "iptu": 50.0,
        "total_price": 1850.0,
        "bedrooms": 2,
        "url": "https://www.vivareal.com.br/imovel/123",
    }
    detail = {"photos": ["https://cdn.test/1.jpg"], "description": "Sol da manhã"}
    listing = WebListing.from_parts(projected, detail)
    assert listing.photos == ("https://cdn.test/1.jpg",)
    assert listing.description == "Sol da manhã"
    assert listing.official_url == "https://www.vivareal.com.br/imovel/123"
    assert listing.to_dict()["total_price"] == 1850.0


def test_listing_without_detail_has_no_media_and_keeps_link():
    projected = {"provider": "epifanioimoveis", "code": "9", "url": "https://epi.test/9", "total_price": None}
    listing = WebListing.from_parts(projected, None)
    assert listing.photos == ()
    assert listing.description is None
    assert listing.official_url == "https://epi.test/9"


def test_listing_drops_non_http_official_url():
    projected = {"provider": "x", "code": "1", "url": "javascript:void(0)"}
    assert WebListing.from_parts(projected, None).official_url is None


def test_listing_cover_photo_is_first_photo():
    projected = {"provider": "x", "code": "1"}
    detail = {"photos": ["https://a.test/1.jpg", "https://a.test/2.jpg"]}
    assert WebListing.from_parts(projected, detail).to_dict()["cover_photo"] == "https://a.test/1.jpg"
    assert WebListing.from_parts(projected, None).to_dict()["cover_photo"] is None


class _Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_cache_returns_value_until_ttl_expires():
    clock = _Clock()
    cache = TtlCache(ttl_seconds=10, clock=clock)
    cache.set(("vivareal", "1"), {"ok": True})
    clock.now = 9.9
    assert cache.get(("vivareal", "1")) == {"ok": True}
    clock.now = 10.0
    assert cache.get(("vivareal", "1")) is None


def test_cache_miss_returns_none():
    assert TtlCache(ttl_seconds=10).get(("nope", "1")) is None


def test_cache_zero_ttl_never_stores():
    cache = TtlCache(ttl_seconds=0)
    cache.set(("p", "1"), {"ok": True})
    assert cache.get(("p", "1")) is None


def test_cache_evicts_oldest_when_full():
    clock = _Clock()
    cache = TtlCache(ttl_seconds=100, clock=clock, max_entries=2)
    cache.set(("p", "1"), {"n": 1})
    clock.now = 1
    cache.set(("p", "2"), {"n": 2})
    clock.now = 2
    cache.set(("p", "3"), {"n": 3})
    assert cache.get(("p", "1")) is None
    assert cache.get(("p", "3")) == {"n": 3}


def test_listing_photos_fall_back_to_search_raw_media_url():
    projected = {"provider": "cabralporto", "code": "1", "raw": {"media_url": "https://cdn.test/capa.jpg"}}
    listing = WebListing.from_parts(projected, None)
    assert listing.photos == ("https://cdn.test/capa.jpg",)


def test_listing_detail_gallery_wins_over_search_media_url():
    projected = {"provider": "vivareal", "code": "1", "raw": {"media_url": "https://cdn.test/capa.jpg"}}
    detail = {"photos": ["https://cdn.test/galeria.jpg"]}
    assert WebListing.from_parts(projected, detail).photos == ("https://cdn.test/galeria.jpg",)
