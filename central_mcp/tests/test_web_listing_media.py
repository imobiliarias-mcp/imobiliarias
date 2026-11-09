"""Tests for choosing a listing's photos from the detail payload, the search payload, or a single cover URL."""

from central_mcp.web.listing import WebListing

PROJECTED = {"provider": "cabralporto", "code": "428", "url": "https://example.com/imovel/428"}


def test_detail_gallery_wins_over_single_cover():
    detail = {"photos": ["https://cdn.test/a.jpg"], "media_url": "https://cdn.test/cover.jpg"}
    assert WebListing.from_parts(PROJECTED, detail).photos == ("https://cdn.test/a.jpg",)


def test_detail_single_cover_is_used_when_gallery_is_missing():
    detail = {"media_url": "https://cdn.test/cover.jpg"}
    listing = WebListing.from_parts(PROJECTED, detail).to_dict()
    assert listing["cover_photo"] == "https://cdn.test/cover.jpg"
    assert listing["photos"] == ["https://cdn.test/cover.jpg"]


def test_search_raw_media_is_used_when_detail_has_nothing():
    projected = {**PROJECTED, "raw": {"media_url": "https://cdn.test/search.jpg"}}
    assert WebListing.from_parts(projected, {}).photos == ("https://cdn.test/search.jpg",)


def test_invalid_detail_cover_is_ignored():
    detail = {"media_url": "javascript:alert(1)"}
    assert WebListing.from_parts(PROJECTED, detail).photos == ()
