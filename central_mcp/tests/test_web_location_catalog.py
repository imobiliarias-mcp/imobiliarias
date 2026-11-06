"""Tests for the persisted catalog of cities and neighborhoods seen in listings."""

from __future__ import annotations

import json
from pathlib import Path

from central_mcp.web.location_catalog import LocationCatalog
from central_mcp.web.locations import ParsedLocation

CATALOG_FILE = "locations.json"


def _names(entries: list[dict[str, str]]) -> set[str]:
    return {entry["name"] for entry in entries}


def test_memory_catalog_is_seeded_with_vale_do_aco_cities() -> None:
    catalog = LocationCatalog.open(None)

    assert _names(catalog.cities()) == {"Timóteo", "Coronel Fabriciano", "Ipatinga"}


def test_observe_inserts_unseen_city_and_neighborhood() -> None:
    catalog = LocationCatalog.open(None)

    catalog.observe([ParsedLocation(city="Timóteo", neighborhood="Olaria")])

    neighborhood_names = _names(catalog.neighborhoods())
    assert "Olaria" in neighborhood_names
    assert catalog.neighborhoods()[0]["city_key"] == "timoteo"


def test_observe_ignores_spelling_variants_of_known_keys() -> None:
    catalog = LocationCatalog.open(None)
    catalog.observe([ParsedLocation(city="Timóteo", neighborhood="OLARIA")])

    catalog.observe([ParsedLocation(city="TIMOTEO", neighborhood="olaria")])

    olaria = [entry for entry in catalog.neighborhoods() if entry["name"].casefold() == "olaria"]
    assert len(olaria) == 1


def test_observe_upgrades_display_name_to_accented_form() -> None:
    catalog = LocationCatalog.open(None)
    catalog.observe([ParsedLocation(city="Timóteo", neighborhood="Funcionarios")])

    catalog.observe([ParsedLocation(city="Timóteo", neighborhood="Funcionários")])

    assert _names(catalog.neighborhoods()) == {"Funcionários"}


def test_observe_without_city_adds_nothing() -> None:
    catalog = LocationCatalog.open(None)

    catalog.observe([ParsedLocation(city=None, neighborhood="Olaria")])

    assert catalog.neighborhoods() == []


def test_resolve_city_accepts_key_or_name() -> None:
    catalog = LocationCatalog.open(None)

    assert catalog.resolve_city("timoteo") == "Timóteo"
    assert catalog.resolve_city("Coronel Fabriciano") == "Coronel Fabriciano"
    assert catalog.resolve_city("Belo Horizonte") is None


def test_catalog_persists_and_reloads_from_data_dir(tmp_path: Path) -> None:
    LocationCatalog.open(tmp_path).observe([ParsedLocation(city="Ipatinga", neighborhood="Veneza")])

    reloaded = LocationCatalog.open(tmp_path)

    assert "Veneza" in _names(reloaded.neighborhoods())
    assert json.loads((tmp_path / CATALOG_FILE).read_text(encoding="utf-8"))


def test_save_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    LocationCatalog.open(tmp_path).observe([ParsedLocation(city="Ipatinga", neighborhood="Veneza")])

    assert sorted(path.name for path in tmp_path.iterdir()) == [CATALOG_FILE]


def test_known_locations_do_not_rewrite_the_file(tmp_path: Path) -> None:
    catalog = LocationCatalog.open(tmp_path)
    catalog.observe([ParsedLocation(city="Ipatinga", neighborhood="Veneza")])
    (tmp_path / CATALOG_FILE).unlink()

    catalog.observe([ParsedLocation(city="Ipatinga", neighborhood="Veneza")])

    assert not (tmp_path / CATALOG_FILE).exists()


def test_corrupt_file_falls_back_to_seeds(tmp_path: Path) -> None:
    (tmp_path / CATALOG_FILE).write_text("{not json", encoding="utf-8")

    catalog = LocationCatalog.open(tmp_path)

    assert _names(catalog.cities()) == {"Timóteo", "Coronel Fabriciano", "Ipatinga"}


def test_unwritable_data_dir_falls_back_to_memory(tmp_path: Path) -> None:
    blocked = tmp_path / "is-a-file"
    blocked.write_text("x", encoding="utf-8")
    catalog = LocationCatalog.open(blocked)

    catalog.observe([ParsedLocation(city="Ipatinga", neighborhood="Veneza")])

    assert "Veneza" in _names(catalog.neighborhoods())
    assert not catalog.is_persistent
