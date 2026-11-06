"""Catalog of cities and neighborhoods observed in listings, persisted as JSON.

The catalog only grows when an unseen city or neighborhood appears. Writes are atomic
(temporary file, then rename). When the data directory is not writable the catalog keeps
working in memory and logs a warning.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from central_mcp.web.locations import ParsedLocation, display_name, location_key

logger = logging.getLogger(__name__)

CATALOG_FILE_NAME = "locations.json"
SEED_CITIES = ("Timóteo", "Coronel Fabriciano", "Ipatinga")


class LocationCatalog:
    """Known cities and neighborhoods, keyed by comparison key, safe for concurrent use."""

    def __init__(self, path: Path | None, cities: dict[str, str], neighborhoods: dict[str, dict[str, str]]) -> None:
        self._path = path
        self._cities = cities
        self._neighborhoods = neighborhoods
        self._persistent = path is not None
        self._lock = threading.Lock()

    @classmethod
    def open(cls, data_dir: Path | None) -> LocationCatalog:
        """Load the catalog from data_dir, seeded with the Vale do Aço cities; memory-only if unusable."""
        cities = {location_key(name): name for name in SEED_CITIES}
        if data_dir is None or not _prepare_directory(data_dir):
            return cls(None, cities, {})
        path = data_dir / CATALOG_FILE_NAME
        stored = _read_stored(path)
        return cls._from_stored(path, cities, stored)

    @classmethod
    def _from_stored(cls, path: Path, seed: dict[str, str], stored: dict[str, Any]) -> LocationCatalog:
        cities = dict(seed)
        for key, name in _string_items(stored.get("cities")):
            cities.setdefault(key, name)
        neighborhoods = {key: dict(value) for key, value in _entry_items(stored.get("neighborhoods"))}
        return cls(path, cities, neighborhoods)

    @property
    def is_persistent(self) -> bool:
        """Whether observations are written to disk."""
        return self._persistent

    def cities(self) -> list[dict[str, str]]:
        """Known cities sorted by name, each with its comparison key."""
        entries = [{"key": key, "name": name} for key, name in self._cities.items()]
        return sorted(entries, key=lambda entry: entry["name"])

    def neighborhoods(self) -> list[dict[str, str]]:
        """Known neighborhoods sorted by name, each with its city key."""
        entries = [
            {"key": key, "name": value["name"], "city_key": value["city_key"]}
            for key, value in self._neighborhoods.items()
        ]
        return sorted(entries, key=lambda entry: entry["name"])

    def resolve_city(self, text: str) -> str | None:
        """Return the canonical city name for a key or name, or None when unknown."""
        return self._cities.get(location_key(text))

    def neighborhood_name(self, city_name: str, neighborhood: str) -> str:
        """Return the best-known spelling of a neighborhood, or the input when never observed."""
        entry = self._neighborhoods.get(self.neighborhood_key(city_name, neighborhood))
        return entry["name"] if entry is not None else neighborhood

    def observe(self, locations: Iterable[ParsedLocation]) -> None:
        """Record locations, persisting only when a city or neighborhood was not known before."""
        with self._lock:
            inserted = [self._observe_one(location) for location in locations]
            if any(inserted):
                self._save()

    @staticmethod
    def neighborhood_key(city_name: str, neighborhood_name: str) -> str:
        """Return the stable key of a neighborhood within its city."""
        return f"{location_key(city_name)}/{location_key(neighborhood_name)}"

    def _observe_one(self, location: ParsedLocation) -> bool:
        if not location.city:
            return False
        city_key = location_key(location.city)
        inserted = self._upsert_city(city_key, location.city)
        if location.neighborhood:
            neighborhood_inserted = self._upsert_neighborhood(city_key, location.neighborhood)
            inserted = inserted or neighborhood_inserted
        return inserted

    def _upsert_city(self, key: str, name: str) -> bool:
        if key in self._cities:
            self._cities[key] = display_name(self._cities[key], name)
            return False
        self._cities[key] = display_name(name)
        return True

    def _upsert_neighborhood(self, city_key: str, name: str) -> bool:
        key = f"{city_key}/{location_key(name)}"
        if key in self._neighborhoods:
            current = self._neighborhoods[key]["name"]
            self._neighborhoods[key]["name"] = display_name(current, name)
            return False
        self._neighborhoods[key] = {"name": display_name(name), "city_key": city_key}
        return True

    def _save(self) -> None:
        if self._path is None:
            return
        payload = {"cities": self._cities, "neighborhoods": self._neighborhoods}
        temporary = self._path.with_name(self._path.name + ".tmp")
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self._path)
        except OSError as exc:
            logger.warning("location catalog not persisted, keeping it in memory: %s", exc)
            self._persistent = False


def _prepare_directory(data_dir: Path) -> bool:
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("location catalog directory unavailable, using memory only: %s", exc)
        return False
    if not os.access(data_dir, os.W_OK):
        logger.warning("location catalog directory is not writable, using memory only: %s", data_dir)
        return False
    return True


def _read_stored(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("ignoring unreadable location catalog %s: %s", path, exc)
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _string_items(raw: Any) -> list[tuple[str, str]]:
    if not isinstance(raw, dict):
        return []
    return [(key, value) for key, value in raw.items() if isinstance(key, str) and isinstance(value, str)]


def _entry_items(raw: Any) -> list[tuple[str, dict[str, str]]]:
    if not isinstance(raw, dict):
        return []
    valid = []
    for key, value in raw.items():
        if isinstance(value, dict) and isinstance(value.get("name"), str) and isinstance(value.get("city_key"), str):
            valid.append((key, {"name": value["name"], "city_key": value["city_key"]}))
    return valid
