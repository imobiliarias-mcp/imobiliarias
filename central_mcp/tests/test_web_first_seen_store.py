"""Unit and integration tests for persistent FirstSeenStore."""

from __future__ import annotations

import concurrent.futures
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from central_mcp.config import AppConfig
from central_mcp.http_app import create_http_app
from central_mcp.server import create_mcp_server
from central_mcp.web.first_seen_store import FIRST_SEEN_FILE_NAME, FirstSeenStore


def test_open_with_none_data_dir_is_memory_only():
    store = FirstSeenStore.open(None)
    assert not store.is_persistent
    timestamp = store.observe("prov", "101")
    assert timestamp != ""
    assert datetime.fromisoformat(timestamp) is not None
    assert store.get("prov", "101") == timestamp


def test_observe_idempotency_returns_original_timestamp(tmp_path: Path):
    store = FirstSeenStore.open(tmp_path)
    timestamp_first = store.observe("prov", "101")
    timestamp_second = store.observe("prov", "101")
    assert timestamp_first == timestamp_second


def test_persistence_and_reload_across_reopen(tmp_path: Path):
    store_one = FirstSeenStore.open(tmp_path)
    timestamp = store_one.observe("prov", "101")
    assert (tmp_path / FIRST_SEEN_FILE_NAME).exists()

    reloaded = FirstSeenStore.open(tmp_path)
    assert reloaded.get("prov", "101") == timestamp
    assert reloaded.observe("prov", "101") == timestamp


def test_atomic_write_leaves_no_temp_files(tmp_path: Path):
    store = FirstSeenStore.open(tmp_path)
    store.observe("prov", "101")
    assert (tmp_path / FIRST_SEEN_FILE_NAME).exists()
    assert not (tmp_path / "first_seen.tmp").exists()
    assert not (tmp_path / "first_seen.json.tmp").exists()


def test_unseen_item_returns_none_from_get(tmp_path: Path):
    store = FirstSeenStore.open(tmp_path)
    assert store.get("prov", "unknown") is None


def test_known_items_do_not_rewrite_file(tmp_path: Path):
    store = FirstSeenStore.open(tmp_path)
    store.observe("prov", "101")
    target_file = tmp_path / FIRST_SEEN_FILE_NAME
    mtime = target_file.stat().st_mtime_ns

    store.observe("prov", "101")
    assert target_file.stat().st_mtime_ns == mtime


def test_empty_file_falls_back_to_empty_dict(tmp_path: Path):
    (tmp_path / FIRST_SEEN_FILE_NAME).write_text("", encoding="utf-8")
    store = FirstSeenStore.open(tmp_path)
    assert store.get("prov", "101") is None
    timestamp = store.observe("prov", "101")
    assert store.get("prov", "101") == timestamp


def test_corrupted_json_falls_back_to_empty_dict(tmp_path: Path):
    (tmp_path / FIRST_SEEN_FILE_NAME).write_text("{malformed json", encoding="utf-8")
    store = FirstSeenStore.open(tmp_path)
    assert store.get("prov", "101") is None


def test_non_dict_json_falls_back_to_empty_dict(tmp_path: Path):
    (tmp_path / FIRST_SEEN_FILE_NAME).write_text('["list", 123]', encoding="utf-8")
    store = FirstSeenStore.open(tmp_path)
    assert store.get("prov", "101") is None


def test_unwritable_directory_falls_back_to_memory(tmp_path: Path):
    blocked_path = tmp_path / "is_file"
    blocked_path.write_text("not a directory", encoding="utf-8")
    store = FirstSeenStore.open(blocked_path)
    assert not store.is_persistent
    timestamp = store.observe("prov", "101")
    assert timestamp != ""
    assert store.get("prov", "101") == timestamp


def test_empty_or_whitespace_code_is_ignored(tmp_path: Path):
    store = FirstSeenStore.open(tmp_path)
    assert store.observe("prov", "") == ""
    assert store.observe("prov", "   ") == ""
    assert store.observe("", "101") == ""
    assert not (tmp_path / FIRST_SEEN_FILE_NAME).exists()


def test_observe_many_batches_persisted_entries(tmp_path: Path):
    store = FirstSeenStore.open(tmp_path)
    results = store.observe_many([
        ("prov1", "101"),
        ("prov2", "202"),
        ("prov1", "101"),
        ("", "303"),
        ("prov3", ""),
        ("prov4", "   "),
    ])
    assert ("prov1", "101") in results
    assert ("prov2", "202") in results
    assert len(results) == 2
    assert store.get("prov1", "101") == results[("prov1", "101")]
    assert store.get("prov2", "202") == results[("prov2", "202")]


def test_thread_safety_concurrent_observes(tmp_path: Path):
    store = FirstSeenStore.open(tmp_path)
    item_count = 50

    def record_entry(idx: int) -> str:
        return store.observe(f"prov_{idx % 5}", f"code_{idx}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        timestamps = list(executor.map(record_entry, range(item_count)))

    assert len(timestamps) == item_count
    for idx in range(item_count):
        assert store.get(f"prov_{idx % 5}", f"code_{idx}") == timestamps[idx]

    persisted = json.loads((tmp_path / FIRST_SEEN_FILE_NAME).read_text(encoding="utf-8"))
    assert len(persisted) == item_count


class FakeRouteService:
    def catalog(self) -> list[dict[str, Any]]:
        return [{"provider_name": "vivareal", "coverage_region": "Vale do Aço"}]

    async def federated_search(self, **kwargs: Any) -> dict[str, Any]:
        item = {
            "provider": "vivareal",
            "code": "123",
            "title": "Apartamento Centro",
            "location": "Centro, Timóteo",
            "rent_price": 1500.0,
            "condo_fee": None,
            "iptu": None,
            "total_price": 1500.0,
            "bedrooms": 2,
            "url": "https://www.vivareal.com.br/imovel/123",
        }
        return {"status": "ok", "providers": [{"provider": "vivareal", "status": "ok"}], "results": [item]}

    async def detail(self, provider: str, property_code: str) -> dict[str, Any]:
        return {
            "title": "Apartamento Centro",
            "url": "https://www.vivareal.com.br/imovel/123",
            "price": "R$ 1.500",
            "photos": ["https://cdn.test/1.jpg"],
            "description": "Belo apartamento",
            "rent_price": 1500.0,
            "condo_fee": None,
            "iptu": None,
            "total_price": 1500.0,
        }

    async def facets(self, provider: str) -> dict[str, Any]:
        return {"cities": [{"name": "Timóteo"}]}


def test_routes_serialize_first_seen_at(tmp_path: Path):
    cfg = AppConfig(
        rate_limit_burst=1000,
        rate_limit_per_minute=100000,
        data_dir=tmp_path,
    )
    service = FakeRouteService()
    app = create_http_app(create_mcp_server(), cfg, service=service)

    with TestClient(app) as client:
        # Search returns first_seen_at ISO string
        search_res = client.get("/api/search")
        assert search_res.status_code == 200
        search_body = search_res.json()
        assert len(search_body["results"]) == 1
        listing = search_body["results"][0]
        first_seen_at = listing.get("first_seen_at")
        assert first_seen_at is not None
        assert datetime.fromisoformat(first_seen_at) is not None

        # Detail of the observed listing returns matching first_seen_at
        detail_res = client.get("/api/listings/vivareal/123")
        assert detail_res.status_code == 200
        detail_body = detail_res.json()
        assert detail_body.get("first_seen_at") == first_seen_at

        # Detail of an unseen listing returns first_seen_at: null
        unseen_res = client.get("/api/listings/vivareal/999")
        assert unseen_res.status_code == 200
        unseen_body = unseen_res.json()
        assert unseen_body.get("first_seen_at") is None
