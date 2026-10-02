"""Offline contract tests for the Epifanio rental adapter."""
import json
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from jsonschema import Draft202012Validator

from rental_bridge.errors import BridgeError
from rental_bridge.providers import epifanioimoveis

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


def _mock_responses(monkeypatch, body):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=body)

    @contextmanager
    def managed_client(**kwargs):
        with httpx.Client(transport=httpx.MockTransport(respond), **kwargs) as client:
            yield client

    monkeypatch.setattr(epifanioimoveis, "managed_httpx", managed_client)
    return requests


def test_search_applies_composed_filters_and_returns_serialized_result(monkeypatch):
    search_html = '<link rel="canonical" href="https://www.epifanioimoveis.com/imovel/locacao/todos/timoteo/"><div class="resultado-vazio">Nenhum imóvel encontrado</div>'
    requests = _mock_responses(monkeypatch, search_html)
    filters = {"city": "timoteo", "property_type": "casa", "minimum_price": 1000, "maximum_price": 2500, "minimum_area": 40, "maximum_area": 100, "bedrooms": 2, "minimum_bedrooms": True, "suites": 1, "minimum_suites": False, "bathrooms": 1, "minimum_bathrooms": False, "parking_spaces": 1, "minimum_parking_spaces": True, "neighborhood_ids": ["9", "15"], "sort_order": "maior_valor", "reference_code": "EP-1", "page": 2}
    result = epifanioimoveis.execute("search", filters)
    query = parse_qs(urlsplit(str(requests[0].url)).query)
    assert query["vmi"] == ["1000"] and query["vma"] == ["2500"]
    assert query["areaMinima"] == ["40"] and query["areaMaxima"] == ["100"]
    assert query["dormitorios"] == ["22"] and query["suites"] == ["1"]
    assert query["banheiros"] == ["1"] and query["vagas"] == ["21"]
    assert query["bairros"] == ["9,15"] and query["ref"] == ["EP-1"]
    assert result["native"]["current_page"] == 2 and result["display"] == []


def test_canonical_search_route_without_results_marker_is_rejected(monkeypatch):
    body = '<link rel="canonical" href="https://www.epifanioimoveis.com/imovel/locacao/todos/timoteo/">'
    _mock_responses(monkeypatch, body)
    with pytest.raises(Exception, match="invalid_content"):
        epifanioimoveis.execute("search", {})


def test_detail_returns_publicly_serialized_property(monkeypatch):
    body = '<link rel="canonical" href="https://www.epifanioimoveis.com/imovel/123"><h1 class="imovel__titulo">Casa</h1>'
    _mock_responses(monkeypatch, body)
    result = epifanioimoveis.execute("detail", {"reference": "123"})
    assert result["native"]["overview"]["property_id"] == "123"
    assert result["display"][0]["url"].startswith("https://www.epifanioimoveis.com/imovel/123")
    _validate_display_reference("epifanioimoveis", result["display"][0]["reference"])


def test_generic_detail_html_is_rejected_before_parsing(monkeypatch):
    _mock_responses(monkeypatch, "<article><h1>News</h1></article>")
    with pytest.raises(Exception, match="invalid_content"):
        epifanioimoveis.execute("detail", {"reference": "123"})


def test_unexpected_search_html_is_rejected(monkeypatch):
    _mock_responses(monkeypatch, "<html><title>Unknown</title></html>")
    with pytest.raises(Exception, match="invalid_content"):
        epifanioimoveis.execute("search", {})


def test_facets_require_locations_selector(monkeypatch):
    body = '<script>dgCidadesBairros = { cidades: [], bairros: [], bairros_value: [] }</script>'
    _mock_responses(monkeypatch, body)
    with pytest.raises(BridgeError, match="invalid_input"):
        epifanioimoveis.execute("facets", {})
    result = epifanioimoveis.execute("facets", {"selector": "locations"})
    assert result["native"]["cities"] == []


def test_spec_declares_all_effective_search_filters():
    spec_path = Path(__file__).resolve().parents[2] / "provider-specs/epifanioimoveis.json"
    spec = json.loads(spec_path.read_text())
    assert spec["filters"]["additionalProperties"] is False
    assert {"minimum_price", "maximum_price", "minimum_area", "maximum_area", "neighborhood_ids", "reference_code"} <= set(spec["filters"]["properties"])
    assert spec["facets"]["required"] == ["selector"]
    assert spec["facets"]["properties"]["selector"]["const"] == "locations"
