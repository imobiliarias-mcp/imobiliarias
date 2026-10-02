import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from jsonschema import Draft202012Validator

import rental_bridge.providers.niltoncorretordeimoveis as provider
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
SEARCH_HTML = '''
<div class="imovelcard" data-link="/imovel/12345">
  <div class="imovelcard__info">
    <span class="imovelcard__info__ref">Ref: REF77 - apartamento</span>
    <span class="imovelcard__info__local">Centro, Timóteo/MG</span>
    <a class="imovelcard__img" href="/imovel/12345" title="Apartamento Centro">
      <img src="https://niltoncorretordeimoveis.com.br/photo.jpg">
    </a>
    <span class="imovelcard__valor__valor">R$ 2.500,00</span>
  </div>
</div>
'''
DETAIL_HTML = '''
<h1>Apartamento Centro</h1>
<div class="imovelcard__info__ref">Ref: REF77</div>
<div class="info__col">Centro, Timóteo/MG</div>
<div class="info__valor">R$ 2.500,00</div>
<div class="info__tag">2 Dormitórios</div>
'''
FACETS_HTML = """cidades : [['timoteo', 'Timóteo']], bairros : [['Centro']], bairros_value : [['centro-17']]};"""


def _client(monkeypatch, body, content_type="text/html"):
    def respond(request):
        return httpx.Response(200, text=body, headers={"content-type": content_type}, request=request)

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_search_applies_all_advertised_filters_and_formats_public_listing(monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=SEARCH_HTML, headers={"content-type": "text/html"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    try:
        result = provider.execute(
            "search",
            {
                "city": "timoteo",
                "property_type": "apartamento",
                "neighborhood_ids": ["17", "18"],
                "bedrooms": 3,
                "min_bedrooms": True,
                "suites": 1,
                "min_suites": True,
                "bathrooms": 2,
                "parking_spaces": 1,
                "min_price": 1200,
                "max_price": 4000,
                "min_area": 45,
                "max_area": 120,
                "sort": "menor_valor",
                "page": 2,
                "reference_code": "REF77",
            },
            client=client,
        )
    finally:
        client.close()

    parameters = parse_qs(urlsplit(str(requests[0].url)).query)
    assert parameters["bairros"] == ["17,18"]
    assert parameters["dormitorios"] == ["23"]
    assert parameters["suites"] == ["21"]
    assert parameters["banheiros"] == ["2"]
    assert parameters["vagas"] == ["1"]
    assert parameters["vmi"] == ["1200"]
    assert parameters["vma"] == ["4000"]
    assert parameters["areaMinima"] == ["45"]
    assert parameters["areaMaxima"] == ["120"]
    assert parameters["ord"] == ["menor_valor"]
    assert parameters["pag"] == ["2"]
    assert parameters["ref"] == ["REF77"]
    assert parameters["reftipo"] == ["exata"]
    native = result["native"]
    assert native["items"][0]["identity"]["reference_code"] == "REF77"
    assert result["display"] == [
        {
            "reference": "12345",
            "url": "https://niltoncorretordeimoveis.com.br/imovel/12345",
            "title": "Apartamento Centro",
            "location": "Centro, Timóteo, MG",
            "price": "R$ 2.500,00",
        }
    ]
    reference_schema = json.loads((ROOT / "provider-specs/niltoncorretordeimoveis.json").read_text())["reference"]
    Draft202012Validator(reference_schema).validate(result["display"][0]["reference"])
    assert json.loads(json.dumps(result, allow_nan=False)) == result


def test_detail_uses_source_parser_and_public_route(monkeypatch):
    requested = []

    def respond(request):
        requested.append(str(request.url))
        return httpx.Response(200, text=DETAIL_HTML, headers={"content-type": "text/html"}, request=request)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    try:
        result = provider.execute("detail", {"reference": "12345"}, client=client)
    finally:
        client.close()

    assert requested[0] == "https://niltoncorretordeimoveis.com.br/imovel/12345"
    assert result["native"]["overview"]["canonical_url"] == requested[0]
    assert result["display"][0]["reference"] == "12345"
    reference_schema = json.loads((ROOT / "provider-specs/niltoncorretordeimoveis.json").read_text())["reference"]
    Draft202012Validator(reference_schema).validate(result["display"][0]["reference"])


@pytest.mark.parametrize("reference", ["0", "abc", "../api", "1" * 33, 123])
def test_invalid_detail_references_fail_contract_and_adapter_validation(reference):
    request = {
        "version": 1, "provider": provider.PROVIDER, "operation": "detail",
        "arguments": {"reference": reference},
    }
    with pytest.raises(BridgeError):
        validate_request(request)
    with pytest.raises(ValueError):
        provider.execute("detail", {"reference": reference}, client=object())


def test_facets_returns_parsed_cities_and_neighborhoods(monkeypatch):
    client = _client(monkeypatch, FACETS_HTML)
    try:
        result = provider.execute("facets", {"selector": "locations"}, client=client)
    finally:
        client.close()

    assert result["native"]["cities"][0]["name"] == "Timóteo"
    assert result["native"]["cities"][0]["neighborhoods"][0]["name"] == "Centro"
    assert result["display"][0]["title"] == "Timóteo"


def test_provider_spec_has_a_closed_search_filter_schema():
    specification = json.loads((ROOT / "provider-specs/niltoncorretordeimoveis.json").read_text())
    assert specification["id"] == "niltoncorretordeimoveis"
    assert specification["filters"]["additionalProperties"] is False
    assert {"city", "neighborhood_ids", "reference_code", "min_price", "min_area"}.issubset(
        specification["filters"]["properties"]
    )
    assert all("description" in schema for schema in specification["filters"]["properties"].values())
    assert specification["reference"]["pattern"] == "^[1-9][0-9]*$"
    assert specification["facets"]["required"] == ["selector"]
