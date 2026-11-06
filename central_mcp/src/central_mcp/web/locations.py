"""Parse free-form listing locations into city and neighborhood, and build stable keys.

Providers report locations in several shapes ("Bairro, Cidade", "Bairro - Cidade/MG",
or no location at all). These helpers reduce them to one comparable form.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

SEPARATOR_PATTERN = re.compile(r"[-,/]")
NON_WORD_PATTERN = re.compile(r"[\W_]+")
STATE_CODE_KEY = "mg"
PREPOSITIONS = frozenset({"de", "da", "do", "das", "dos", "e"})


@dataclass(frozen=True)
class ParsedLocation:
    """City and neighborhood extracted from one listing; either may be absent."""

    city: str | None
    neighborhood: str | None


def parse_location(
    location: str | None,
    *,
    neighborhood: str | None = None,
    city: str | None = None,
    known_cities: Iterable[str] = (),
) -> ParsedLocation:
    """Return the city and neighborhood, preferring structured fields over free text."""
    structured_city = _clean(city)
    structured_neighborhood = _clean(neighborhood)
    if structured_city or structured_neighborhood:
        return ParsedLocation(city=structured_city, neighborhood=structured_neighborhood)
    tokens = _tokens(location)
    return _from_tokens(tokens, frozenset(location_key(name) for name in known_cities))


def location_key(text: str) -> str:
    """Return a comparison key: no accents, lowercase, punctuation and spacing collapsed."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(char for char in decomposed if not unicodedata.combining(char))
    return NON_WORD_PATTERN.sub(" ", without_marks.casefold()).strip()


def display_name(*candidates: str) -> str:
    """Pick the most readable spelling among variants and return it in Title Case."""
    cleaned = [value for value in (_clean(candidate) for candidate in candidates) if value]
    if not cleaned:
        return ""
    return _title_case(max(cleaned, key=_readability))


def _from_tokens(tokens: list[str], known_keys: frozenset[str]) -> ParsedLocation:
    if not tokens:
        return ParsedLocation(city=None, neighborhood=None)
    city_index = _known_city_index(tokens, known_keys)
    if city_index is not None:
        remaining = tokens[:city_index] + tokens[city_index + 1 :]
        return ParsedLocation(city=tokens[city_index], neighborhood=remaining[0] if remaining else None)
    if len(tokens) >= 2:
        return ParsedLocation(city=tokens[-1], neighborhood=tokens[0])
    return ParsedLocation(city=None, neighborhood=tokens[0])


def _known_city_index(tokens: list[str], known_keys: frozenset[str]) -> int | None:
    for index, token in enumerate(tokens):
        if location_key(token) in known_keys:
            return index
    return None


def _tokens(location: str | None) -> list[str]:
    if location is None:
        return []
    parts = (_clean(part) for part in SEPARATOR_PATTERN.split(location))
    return [part for part in parts if part and location_key(part) != STATE_CODE_KEY]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    collapsed = " ".join(value.split())
    return collapsed or None


def _readability(text: str) -> tuple[bool, bool, int]:
    has_accent = any(ord(char) > 127 for char in text)
    is_mixed_case = not text.isupper() and not text.islower()
    return (has_accent, is_mixed_case, len(text))


def _title_case(text: str) -> str:
    words = text.split(" ")
    return " ".join(_title_word(word, index) for index, word in enumerate(words))


def _title_word(word: str, index: int) -> str:
    lowered = word.lower()
    if index > 0 and lowered in PREPOSITIONS:
        return lowered
    return lowered[:1].upper() + lowered[1:]
