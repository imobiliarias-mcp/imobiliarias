import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

import rental_bridge.providers.vivareal as provider
from rental_bridge.contracts import PROVIDER_IDS
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
    "search": {
        "totalCount": 17,
        "result": {
            "listings": [
                {
                    "listing": {
                        "id": "123",
                        "externalId": "EXT-9",
                        "title": "Apartamento Centro",
                        "address": {"neighborhood": "Centro", "city": "Timóteo", "stateAcronym": "MG"},
                        "pricingInfos": [
                            {
                                "businessType": "RENTAL",
                                "price": 2400,
                                "monthlyCondoFee": 500,
                                "yearlyIptu": 1200,
                                "rentalInfo": {"monthlyRentalTotalPrice": 2900},
                            }
                        ],
                        "usableAreas": [65],
                        "bedrooms": [2],
                        "bathrooms": [1],
                        "parkingSpaces": [1],
                    },
                    "link": {"href": "/imovel/123/apartamento-centro", "name": "Apartamento Centro"},
                    "medias": [{}],
                    "account": {"name": "Imobiliária"},
                }
            ]
        },
    }
}
DETAIL_HTML = '''
<h1>Apartamento Centro</h1>
<script type="application/ld+json">
{"@context":"https://schema.org","@type": "Product","name":"Apartamento Centro","sku":"123","description":"Descrição","image":[],"offers":{"url":"https://www.vivareal.com.br/imovel/123/apartamento-centro"}}
</script>
'''


def _client(monkeypatch, handler):
    def respond(request):
        payload = handler(request)
        if isinstance(payload, str):
            return httpx.Response(200, text=payload, headers={"content-type": "text/html"}, request=request)
        return httpx.Response(200, json=payload, request=request)

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_search_applies_all_supported_filters_and_keeps_public_fields(monkeypatch):
    requests = []
    client = _client(monkeypatch, lambda request: requests.append(request) or SEARCH_PAYLOAD)
    try:
        result = provider.execute(
            "search",
            {
                "location_id": "BR>Minas Gerais>NULL>Ipatinga",
                "city": "Ipatinga",
                "state": "Minas Gerais",
                "property_type": "APARTMENT",
                "bedrooms": [2, 3],
                "bathrooms": [1],
                "parking_spaces": [1, 2],
                "min_price": 1000,
                "max_price": 3500,
                "min_area": 40,
                "max_area": 140,
                "sort": "LOWEST_PRICE",
                "size": 20,
                "offset": 20,
            },
            client=client,
        )
    finally:
        client.close()

    parameters = parse_qs(urlsplit(str(requests[0].url)).query)
    assert parameters["addressLocationId"] == ["BR>Minas Gerais>NULL>Ipatinga"]
    assert parameters["addressCity"] == ["Ipatinga"]
    assert parameters["addressState"] == ["Minas Gerais"]
    assert parameters["bedrooms"] == ["2,3"]
    assert parameters["bathrooms"] == ["1"]
    assert parameters["parkingSpaces"] == ["1,2"]
    assert parameters["priceMin"] == ["1000"]
    assert parameters["priceMax"] == ["3500"]
    assert parameters["usableAreasMin"] == ["40"]
    assert parameters["usableAreasMax"] == ["140"]
    assert parameters["unitTypes"] == ["APARTMENT"]
    assert parameters["sort"] == ["LOWEST_PRICE"]
    assert parameters["page"] == ["2"]
    assert parameters["size"] == ["20"]
    assert parameters["from"] == ["20"]
    assert result["native"]["total_count"] == 17
    assert result["native"]["listings"][0]["canonical_url"] == "https://www.vivareal.com.br/imovel/123/apartamento-centro"
    assert result["display"][0]["price"] == 2400
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_search_does_not_invent_unknown_totals_prices_or_physical_values(monkeypatch):
    payload = {"search": {"result": {"listings": [{"listing": {"id": "2"}, "link": {"href": "/imovel/2/casa"}}]}}}
    client = _client(monkeypatch, lambda request: payload)
    try:
        result = provider.execute("search", {}, client=client)
    finally:
        client.close()

    listing = result["native"]["listings"][0]
    assert "total_count" not in result["native"]
    assert listing["pricing"].get("monthly_rent") is None
    assert all(value is None for value in listing["features"].values())
    assert result["display"][0].get("price") is None


def test_explicit_zero_rent_is_preserved_in_native_and_display(monkeypatch):
    payload = json.loads(json.dumps(SEARCH_PAYLOAD))
    raw_listing = payload["search"]["result"]["listings"][0]["listing"]
    raw_listing["pricingInfos"] = [{"businessType": "RENTAL", "price": 0}]
    client = _client(monkeypatch, lambda request: payload)
    try:
        result = provider.execute("search", {}, client=client)
    finally:
        client.close()

    assert result["native"]["listings"][0]["pricing"]["monthly_rent"] == 0
    assert result["display"][0]["price"] == 0


def test_detail_accepts_only_public_property_url_and_omits_unknown_cost(monkeypatch):
    requested = []
    client = _client(monkeypatch, lambda request: requested.append(request) or DETAIL_HTML)
    try:
        result = provider.execute(
            "detail",
            {"reference": "https://www.vivareal.com.br/imovel/123/apartamento-centro"},
            client=client,
        )
    finally:
        client.close()

    assert str(requested[0].url).startswith("https://www.vivareal.com.br/imovel/123/")
    assert result["native"]["summary"]["canonical_url"] == str(requested[0].url)
    assert result["native"]["summary"]["pricing"].get("monthly_rent") is None
    assert result["display"][0]["reference"] == "https://www.vivareal.com.br/imovel/123/apartamento-centro"


def test_location_facets_use_glue_autocomplete(monkeypatch):
    requests = []
    payload = {
        "result": [
            {
                "category": "city",
                "address": {
                    "locationId": "BR>Minas Gerais>NULL>Timoteo",
                    "city": "Timóteo",
                    "state": "Minas Gerais",
                    "point": {"lat": -19.58, "lon": -42.64},
                },
            }
        ]
    }
    client = _client(monkeypatch, lambda request: requests.append(request) or payload)
    try:
        result = provider.execute("facets", {"selector": "location_suggestions", "query": "Timóteo", "size": 5}, client=client)
    finally:
        client.close()

    parameters = parse_qs(urlsplit(str(requests[0].url)).query)
    assert parameters["q"] == ["Timóteo"]
    assert parameters["size"] == ["5"]
    assert result["native"][0]["location_id"] == "BR>Minas Gerais>NULL>Timoteo"
    assert result["display"][0]["title"] == "Timóteo"


def test_missing_listings_structure_is_not_a_legitimate_empty_search():
    for payload in [{'search': {}}, {'search': {'result': {}}}, {'search': {'result': {'listings': None}}}]:
        with pytest.raises(BridgeError, match='invalid_content'):
            provider._validate_api_payload('/v2/listings', payload)
    provider._validate_api_payload('/v2/listings', {'search': {'result': {'listings': []}}})


def test_provider_spec_has_closed_filters_and_public_detail_schema():
    specification = json.loads((ROOT / "provider-specs/vivareal.json").read_text())
    assert specification["id"] == "vivareal"
    assert specification["filters"]["additionalProperties"] is False
    assert specification["filters"]["properties"]["property_type"]["enum"] == ["ALL", "APARTMENT", "HOME"]
    assert specification["reference"]["format"] == "uri"
    assert specification["facets"]["properties"]["selector"]["const"] == "location_suggestions"
    assert all("description" in schema for schema in specification["filters"]["properties"].values())
