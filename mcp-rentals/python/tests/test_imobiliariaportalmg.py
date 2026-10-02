"""Offline contract tests for the Portal Imóveis MG adapter."""
import json
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from jsonschema import Draft202012Validator

from rental_bridge.errors import BridgeError
from rental_bridge.providers import imobiliariaportalmg

PROVIDER_IDS = ["alecorretoramg", "arthusoimoveis", "cabralporto", "casalinhares", "epifanioimoveis", "helenaimoveis", "imobiliariaportalmg", "imobiliariavaleinvest", "imovelweb", "marcioimoveis", "minascaixaimoveis", "niltoncorretordeimoveis", "novaimobiliaria", "veraimobiliaria", "vivareal"]


@pytest.fixture(autouse=True)
def _contracts(monkeypatch, tmp_path):
    specs_path = Path(__file__).resolve().parents[2] / "provider-specs"
    providers = [_load_provider_spec(specs_path, provider_id) for provider_id in PROVIDER_IDS]
    contract_path = tmp_path / "providers.json"
    contract_path.write_text(json.dumps({"version": 1, "providers": providers}))
    monkeypatch.setenv("RENTAL_CONTRACTS", str(contract_path))


def _load_provider_spec(specs_path, provider_id):
    spec_path = specs_path / f"{provider_id}.json"
    if spec_path.exists():
        return json.loads(spec_path.read_text())
    return {"id": provider_id, "label": provider_id, "filters": {"type": "object"}, "reference": {"type": "string"}, "facets": None, "limitations": [], "public_hosts": ["invalid.example"], "detail_path_pattern": "^$"}


def _validate_display_reference(provider_id, reference):
    specs_path = Path(__file__).resolve().parents[2] / "provider-specs"
    spec = _load_provider_spec(specs_path, provider_id)
    Draft202012Validator(spec["reference"]).validate(reference)


def _mock_responses(monkeypatch, responder):
    requests = []

    def respond(request):
        requests.append(request)
        return responder(request)

    @contextmanager
    def managed_client(**kwargs):
        with httpx.Client(transport=httpx.MockTransport(respond), **kwargs) as client:
            yield client

    monkeypatch.setattr(imobiliariaportalmg, "managed_httpx", managed_client)
    return requests


def test_search_uses_full_filter_and_offset_builder(monkeypatch):
    body = "<div>Nenhum imóvel encontrado</div>"
    requests = _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    filters = {"city_id": "2371", "neighborhood": "Centro", "category_id": "1", "subcategory_id": "12", "bedrooms": 2, "suites": 1, "garages": 1, "reference": "PM-1", "minimum_price": 1000, "maximum_price": 2500, "page": 2, "page_size": 20, "sort_order": "maior_valor"}
    result = imobiliariaportalmg.execute("search", filters)
    query = parse_qs(urlsplit(str(requests[0].url)).query)
    assert query["cidade_id"] == ["2371"] and query["bairro"] == ["Centro"]
    assert query["tipo"] == ["1"] and query["subtipo"] == ["12"]
    assert query["valor"] == ["1000-2500.00"] and query["pagina"] == ["20"]
    assert result["native"]["listings"] == [] and result["display"] == []


def test_detail_returns_serialized_public_property(monkeypatch):
    body = '<h1 class="imovel__titulo">REF: 608 – Casas Bromélias – Timóteo – MG</h1><div class="imovel__valor-valor">R$ 1.200,00</div>'
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    result = imobiliariaportalmg.execute("detail", {"reference": "608"})
    assert result["native"]["property_id"] == "608"
    assert result["display"][0]["url"].endswith("imoveis_detalhes.php?id=608")
    _validate_display_reference("imobiliariaportalmg", result["display"][0]["reference"])


def test_search_display_reference_matches_detail_reference_schema(monkeypatch):
    body = '<li class="li-imovel"><a href="imoveis_detalhes.php?id=608"></a><span class="li-imovel__ref">REF AB-1</span><span class="li-imovel__categoria">Casa</span><span class="li-imovel__bairro">Centro</span><span class="li-imovel__cidade">Timóteo</span><span class="li-imovel__valor">R$ 1.200,00</span><a class="li-imovel__link-informacoes" href="imoveis_detalhes.php?id=608">Mais</a></li>'
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    result = imobiliariaportalmg.execute("search", {})
    _validate_display_reference("imobiliariaportalmg", result["display"][0]["reference"])


def test_generic_detail_html_is_rejected_before_parsing(monkeypatch):
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text='<h1 class="imovel__titulo">Casa</h1>'))
    with pytest.raises(Exception, match="invalid_content"):
        imobiliariaportalmg.execute("detail", {"reference": "608"})


def test_unexpected_search_html_is_rejected(monkeypatch):
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text="<html><title>Unknown</title></html>"))
    with pytest.raises(Exception, match="invalid_content"):
        imobiliariaportalmg.execute("search", {})


def test_facets_require_explicit_all_selector(monkeypatch):
    def respond(request):
        if request.method == "GET":
            return httpx.Response(200, text='<select id="sl-cidade"></select>')
        return httpx.Response(200, text="[]")

    _mock_responses(monkeypatch, respond)
    with pytest.raises(BridgeError, match="invalid_input"):
        imobiliariaportalmg.execute("facets", {})
    result = imobiliariaportalmg.execute("facets", {"selector": "all"})
    assert result["native"] == {"cities": [], "neighborhoods": [], "categories": []}


def test_spec_declares_filter_schema_and_facet_request():
    spec_path = Path(__file__).resolve().parents[2] / "provider-specs/imobiliariaportalmg.json"
    spec = json.loads(spec_path.read_text())
    assert spec["filters"]["additionalProperties"] is False
    assert {"minimum_price", "maximum_price", "page", "page_size", "subcategory_id"} <= set(spec["filters"]["properties"])
    assert spec["facets"]["required"] == ["selector"]
    assert spec["facets"]["properties"]["selector"]["const"] == "all"
