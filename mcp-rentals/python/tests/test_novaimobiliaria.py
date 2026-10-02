import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from jsonschema import Draft202012Validator

import rental_bridge.providers.novaimobiliaria as provider
from rental_bridge.contracts import PROVIDER_IDS, validate_request
from rental_bridge.errors import BridgeError
from rental_bridge.serialization.projection import clean_projection
from rental_bridge.worker import _validate_output

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def install_contract_registry(monkeypatch, tmp_path):
    specifications = []
    for provider_id in PROVIDER_IDS:
        path = ROOT / "provider-specs" / f"{provider_id}.json"
        if path.exists():
            specifications.append(json.loads(path.read_text()))
            continue
        specifications.append({"id": provider_id, "public_hosts": [], "detail_path_pattern": "^$"})
    generated = json.loads((ROOT / "dist/contracts/providers.json").read_text())
    contract_path = tmp_path / "providers.json"
    contract_path.write_text(json.dumps({
        "version": 1, "providers": specifications, "worker_response": generated["worker_response"]
    }))
    monkeypatch.setenv("RENTAL_CONTRACTS", str(contract_path))
    original_execute = provider.execute

    def execute_and_validate(operation, arguments, **kwargs):
        result = original_execute(operation, arguments, **kwargs)
        response = {"version": 1, "status": "ok", **result}
        response["display"] = list(map(clean_projection, response["display"]))
        _validate_output(response, provider.PROVIDER)
        return result

    monkeypatch.setattr(provider, "execute", execute_and_validate)
SEARCH_PAYLOAD = {
    "meta": {"pagination": {"total": 12, "per_page": 10, "current_page": 1, "total_pages": 2}},
    "data": [
        {
            "id": "123",
            "reference": "N-77",
            "url": "/imovel/apartamento-centro-123",
            "title": "Apartamento Centro",
            "price": "R$ 2.500,00",
            "address": {"formatted": "Centro, Timóteo/MG"},
        }
    ],
}
DETAIL_PAYLOAD = {
    "data": {
        "id": "123",
        "reference": "N-77",
        "title": "Apartamento Centro",
        "price": "R$ 2.500,00",
        "url": "/imovel/apartamento-centro-123",
        "address": {"formatted": "Centro, Timóteo/MG"},
    }
}


def _client(monkeypatch, responder):
    def respond(request):
        payload = responder(request)
        return httpx.Response(200, json=payload, request=request)

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_search_applies_api_filters_and_offset_through_source_builder(monkeypatch):
    requests = []
    client = _client(monkeypatch, lambda request: requests.append(request) or SEARCH_PAYLOAD)
    try:
        result = provider.execute(
            "search",
            {
                "city": "timoteo-mg",
                "property_type": "apartamento",
                "min_price": 1000,
                "max_price": 4000,
                "min_area": 45,
                "max_area": 120,
                "bedrooms": 3,
                "min_bedrooms": True,
                "suites": 1,
                "min_suites": True,
                "garages": 2,
                "min_garages": True,
                "offset": 10,
                "limit": 10,
                "sort": "-created_at,id",
            },
            client=client,
        )
    finally:
        client.close()

    parameters = parse_qs(urlsplit(str(requests[0].url)).query)
    assert parameters["filter[by_neighborhood_or_city_slug]"] == ["timoteo-mg"]
    assert parameters["filter[by_type_or_subtype_slug]"] == ["apartamento"]
    assert parameters["filter[by_higher_than_price]"] == ["1000"]
    assert parameters["filter[by_lower_than_price]"] == ["4000"]
    assert parameters["filter[by_area][greater_equals]"] == ["45"]
    assert parameters["filter[by_area][lower_equals]"] == ["120"]
    assert parameters["filter[by_room_greater_equals][bedroom]"] == ["3"]
    assert parameters["filter[by_room_greater_equals][suite]"] == ["1"]
    assert parameters["filter[by_room_greater_equals][garage]"] == ["2"]
    assert parameters["offset"] == ["10"]
    assert parameters["limit"] == ["10"]
    assert parameters["sort"] == ["-created_at,id"]
    assert result["display"][0]["reference"] == "N-77"
    reference_schema = json.loads((ROOT / "provider-specs/novaimobiliaria.json").read_text())["reference"]
    Draft202012Validator(reference_schema).validate(result["display"][0]["reference"])
    assert result["display"][0]["url"] == "https://jnovaimobiliaria.com.br/imovel/apartamento-centro-123"
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_detail_uses_reference_and_returns_public_fields(monkeypatch):
    requests = []
    client = _client(monkeypatch, lambda request: requests.append(request) or DETAIL_PAYLOAD)
    try:
        result = provider.execute("detail", {"reference": "123"}, client=client)
    finally:
        client.close()

    assert str(requests[0].url).endswith("/api/properties/123")
    assert result["native"]["identity"]["reference"] == "N-77"
    assert result["display"][0]["title"] == "Apartamento Centro"
    assert result["display"][0]["reference"] == "N-77"
    reference_schema = json.loads((ROOT / "provider-specs/novaimobiliaria.json").read_text())["reference"]
    Draft202012Validator(reference_schema).validate(result["display"][0]["reference"])


@pytest.mark.parametrize("reference", ["../api", "A/B", "A" * 129, 123])
def test_invalid_detail_reference_fails_before_worker_or_api(reference):
    request = {
        "version": 1, "provider": provider.PROVIDER, "operation": "detail",
        "arguments": {"reference": reference},
    }
    with pytest.raises(BridgeError):
        validate_request(request)
    with pytest.raises(ValueError):
        provider.execute("detail", {"reference": reference}, client=object())


def test_locations_facets_use_both_catalog_endpoints(monkeypatch):
    def catalog(request):
        if request.url.path.endswith("/filters/states"):
            return {"data": [{"id": 1, "name": "Minas Gerais", "acronym": "MG", "cities": [{"id": 2, "name": "Timóteo"}]}]}
        return {"data": [{"id": 3, "name": "Centro"}]}

    client = _client(monkeypatch, catalog)
    try:
        result = provider.execute("facets", {"selector": "locations"}, client=client)
    finally:
        client.close()

    assert result["native"]["states"][0]["cities"][0]["name"] == "Timóteo"
    assert result["native"]["neighborhoods"][0]["name"] == "Centro"


def test_provider_spec_has_closed_filters_and_locations_facets():
    specification = json.loads((ROOT / "provider-specs/novaimobiliaria.json").read_text())
    assert specification["id"] == "novaimobiliaria"
    assert specification["filters"]["additionalProperties"] is False
    assert {"offset", "limit", "min_area", "max_area", "min_price", "max_price"}.issubset(
        specification["filters"]["properties"]
    )
    assert specification["facets"]["type"] == "object"
    assert specification["facets"]["required"] == ["selector"]
    assert specification["reference"]["pattern"] == "^[A-Za-z0-9_-]+$"
    assert all("description" in schema for schema in specification["filters"]["properties"].values())
