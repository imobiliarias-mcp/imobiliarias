import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

import rental_bridge.providers.veraimobiliaria as provider
from rental_bridge.contracts import PROVIDER_IDS
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
<div class="card">
  <a href="/imovel/1197/apartamento-centro.html">Apartamento</a>
  <span class="endereco">Centro, Timóteo/MG</span>
  <span class="preco">R$ 2.500,00</span>
</div>
'''
DETAIL_HTML = '''
<div class="titulo">Apartamento Centro</div>
<div class="detalhes"><h1>R$ 2.500,00</h1></div>
<div class="localizacao"><a href="https://maps.example/">Rua A, 1, Centro - Timóteo/MG</a></div>
<div id="detalhes">Área construída: 70 m²</div>
'''


def _client(monkeypatch, handler):
    def respond(request):
        status, body = handler(request)
        return httpx.Response(status, text=body, headers={"content-type": "text/html"}, request=request)

    return httpx.Client(transport=httpx.MockTransport(respond))


def test_search_forwards_every_supported_filter_without_postfiltering(monkeypatch):
    requests = []
    client = _client(monkeypatch, lambda request: requests.append(request) or (200, SEARCH_HTML))
    try:
        result = provider.execute(
            "search",
            {
                "city_id": 4,
                "property_type": 1,
                "neighborhood_id": 22,
                "bedrooms": 3,
                "min_price": 1000,
                "max_price": 5000,
                "page": 2,
            },
            client=client,
        )
    finally:
        client.close()

    request_url = urlsplit(str(requests[0].url))
    parameters = parse_qs(request_url.query, keep_blank_values=True)
    assert request_url.path == "/imoveis/pagina_2.html"
    assert parameters["txtcdcidadeBsc"] == ["4"]
    assert parameters["txtcdtpimovelBsc"] == ["1"]
    assert parameters["txtcdbairrocidadeBsc"] == ["22"]
    assert parameters["quartos"] == ["3"]
    assert parameters["faixavalor"] == ["1000a5000"]
    assert len(result["native"]["items"]) == 1
    assert result["display"][0]["url"] == "https://www.veraimobiliaria.com.br/imovel/1197/apartamento-centro.html"
    assert result["display"][0]["reference"] == "1197"


def test_detail_uses_numeric_id_and_canonical_public_url(monkeypatch):
    requested = []
    client = _client(monkeypatch, lambda request: requested.append(request) or (200, DETAIL_HTML))
    try:
        result = provider.execute("detail", {"reference": "1197"}, client=client)
    finally:
        client.close()

    assert str(requested[0].url) == "https://www.veraimobiliaria.com.br/imovel/1197.html"
    assert result["native"]["overview"]["title"] == "Apartamento Centro"
    assert result["display"][0]["reference"] == "1197"
    assert result["display"][0]["url"] == str(requested[0].url)


def test_city_and_neighborhood_facets_preserve_required_city_id(monkeypatch):
    def responder(request):
        if request.method == "POST":
            assert request.url.path == "/asp/ajax/bairros2.asp"
            assert request.content.decode() == "cidade=4&tpnegocio=1&tpimovel=3&tabindex=18"
            return 200, '<option value="22">Centro</option>'
        return 200, '<select name="txtcdcidadeBsc"><option value="4">Ipatinga</option></select>'

    client = _client(monkeypatch, responder)
    try:
        cities = provider.execute("facets", {"selector": "cities"}, client=client)
        neighborhoods = provider.execute(
            "facets", {"selector": "neighborhoods", "city_id": 4, "property_type": 3}, client=client
        )
    finally:
        client.close()

    assert cities["native"]["cities"][0]["name"] == "Ipatinga"
    assert neighborhoods["native"]["neighborhoods"][0]["name"] == "Centro"


def test_provider_spec_has_closed_filter_and_city_required_neighborhood_facets():
    specification = json.loads((ROOT / "provider-specs/veraimobiliaria.json").read_text())
    assert specification["id"] == "veraimobiliaria"
    assert specification["filters"]["additionalProperties"] is False
    assert specification["facets"]["type"] == "object"
    assert all("description" in schema for schema in specification["filters"]["properties"].values())
    neighborhood_schema = next(
        schema for schema in specification["facets"]["oneOf"]
        if schema["properties"]["selector"].get("const") == "neighborhoods"
    )
    assert "city_id" in neighborhood_schema["required"]
