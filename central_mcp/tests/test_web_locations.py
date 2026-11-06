"""Tests for parsing free-form listing locations and building stable location keys."""

from __future__ import annotations

import pytest

from central_mcp.web.locations import (
    ParsedLocation,
    display_name,
    location_key,
    parse_location,
)

KNOWN_CITIES = ("Timóteo", "Coronel Fabriciano", "Ipatinga")


@pytest.mark.parametrize(
    ("raw", "expected_city", "expected_neighborhood"),
    [
        ("Olaria, Timóteo", "Timóteo", "Olaria"),
        ("Olaria, Timóteo / MG", "Timóteo", "Olaria"),
        ("Funcionários - Timóteo/MG", "Timóteo", "Funcionários"),
        ("OLARIA - TIMÓTEO/MG", "TIMÓTEO", "OLARIA"),
        ("Timóteo", "Timóteo", None),
        ("Bairro Centro, Coronel Fabriciano", "Coronel Fabriciano", "Bairro Centro"),
    ],
)
def test_parse_location_handles_each_known_format(
    raw: str, expected_city: str | None, expected_neighborhood: str | None
) -> None:
    parsed = parse_location(raw, known_cities=KNOWN_CITIES)

    assert parsed == ParsedLocation(city=expected_city, neighborhood=expected_neighborhood)


def test_parse_location_prefers_structured_fields_over_text() -> None:
    parsed = parse_location(
        "Ignorado, Outro",
        neighborhood="Veneza",
        city="Ipatinga",
        known_cities=KNOWN_CITIES,
    )

    assert parsed == ParsedLocation(city="Ipatinga", neighborhood="Veneza")


@pytest.mark.parametrize("raw", [None, "", "   ", " - / , "])
def test_parse_location_returns_empty_location_for_blank_input(raw: str | None) -> None:
    parsed = parse_location(raw, known_cities=KNOWN_CITIES)

    assert parsed == ParsedLocation(city=None, neighborhood=None)


def test_parse_location_keeps_unknown_city_as_last_token() -> None:
    parsed = parse_location("Centro, Belo Horizonte", known_cities=KNOWN_CITIES)

    assert parsed == ParsedLocation(city="Belo Horizonte", neighborhood="Centro")


def test_parse_location_treats_lone_unknown_token_as_neighborhood() -> None:
    parsed = parse_location("Olaria", known_cities=KNOWN_CITIES)

    assert parsed == ParsedLocation(city=None, neighborhood="Olaria")


def test_location_key_ignores_accents_case_and_punctuation() -> None:
    assert location_key("Funcionários") == location_key("FUNCIONARIOS")
    assert location_key("  Coronel   Fabriciano ") == location_key("coronel-fabriciano")


def test_location_key_drops_state_suffix_free_text_is_not_mangled() -> None:
    assert location_key("Timóteo / MG") == "timoteo mg"


def test_display_name_prefers_accented_mixed_case_form() -> None:
    assert display_name("OLARIA", "Olaria") == "Olaria"
    assert display_name("Funcionarios", "Funcionários") == "Funcionários"


def test_display_name_title_cases_and_lowercases_prepositions() -> None:
    assert display_name("NOSSA SENHORA DE FÁTIMA") == "Nossa Senhora de Fátima"


def test_display_name_skips_empty_candidates() -> None:
    assert display_name("", "  ", "Ipatinga") == "Ipatinga"
