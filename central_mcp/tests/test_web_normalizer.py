"""Tests for normalizing provider media, descriptions and official URLs."""

import pytest

from central_mcp.web.normalizer import (
    MAX_DESCRIPTION_CHARS,
    normalize_description,
    normalize_http_url,
    normalize_photos,
)


def test_photos_from_list_of_strings():
    raw = {"photos": ["https://cdn.example.com/a.jpg", "https://cdn.example.com/b.jpg"]}
    assert normalize_photos(raw) == (
        "https://cdn.example.com/a.jpg",
        "https://cdn.example.com/b.jpg",
    )


def test_photos_fall_back_to_images_and_gallery_keys():
    assert normalize_photos({"images": ["https://x.test/1.jpg"]}) == ("https://x.test/1.jpg",)
    assert normalize_photos({"gallery": ["https://x.test/2.jpg"]}) == ("https://x.test/2.jpg",)


def test_photos_accepts_dicts_with_url_key():
    raw = {"photos": [{"url": "https://x.test/1.jpg", "alt": "sala"}, {"src": "https://x.test/2.jpg"}]}
    assert normalize_photos(raw) == ("https://x.test/1.jpg", "https://x.test/2.jpg")


def test_photos_drops_invalid_urls_and_duplicates():
    raw = {"photos": ["javascript:alert(1)", "", None, "https://x.test/a.jpg", "https://x.test/a.jpg"]}
    assert normalize_photos(raw) == ("https://x.test/a.jpg",)


@pytest.mark.parametrize("raw", [{}, {"photos": None}, {"photos": "https://x.test/a.jpg"}, {"photos": []}])
def test_photos_empty_when_absent_or_wrong_type(raw):
    assert normalize_photos(raw) == ()


def test_description_trimmed_and_capped():
    assert normalize_description({"description": "  Sala ampla  "}) == "Sala ampla"
    long_text = "a" * (MAX_DESCRIPTION_CHARS + 50)
    assert len(normalize_description({"description": long_text})) == MAX_DESCRIPTION_CHARS


@pytest.mark.parametrize("raw", [{}, {"description": "   "}, {"description": 42}])
def test_description_none_when_blank_or_not_text(raw):
    assert normalize_description(raw) is None


@pytest.mark.parametrize(
    "value, expected",
    [
        ("https://www.vivareal.com.br/imovel/1", "https://www.vivareal.com.br/imovel/1"),
        ("  http://example.com/x  ", "http://example.com/x"),
        ("javascript:alert(1)", None),
        ("/imovel/1", None),
        ("https://", None),
        (None, None),
        (123, None),
    ],
)
def test_http_url_validation(value, expected):
    assert normalize_http_url(value) == expected


def test_cover_falls_back_to_single_media_url_from_search_payload():
    from central_mcp.web.normalizer import normalize_cover_fallback

    assert normalize_cover_fallback({"media_url": "https://cdn.test/cover.jpg"}) == ("https://cdn.test/cover.jpg",)
    assert normalize_cover_fallback({"media_url": "javascript:x"}) == ()
    assert normalize_cover_fallback({}) == ()
