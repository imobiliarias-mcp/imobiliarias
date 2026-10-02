"""Offline contract tests for the Helena rental adapter."""
import json
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from jsonschema import Draft202012Validator

from rental_bridge.errors import BridgeError
from rental_bridge.providers import helenaimoveis

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

    monkeypatch.setattr(helenaimoveis, "managed_httpx", managed_client)
    return requests


def test_search_applies_composed_filters_and_serializes_result(monkeypatch):
    body = '<link rel="canonical" href="https://www.helenaimoveis.com.br/imovel/locacao/todos/timoteo/"><div class="resultado-vazio">Nenhum imóvel encontrado</div>'
    requests = _mock_responses(monkeypatch, body)
    filters = {"city": "timoteo", "neighborhood": "centro", "property_type": "casa", "minimum_price": 1000, "maximum_price": 2500, "minimum_area": 40, "maximum_area": 100, "bedrooms": 2, "minimum_bedrooms": True, "suites": 1, "minimum_suites": False, "bathrooms": 1, "minimum_bathrooms": False, "parking_spaces": 1, "minimum_parking_spaces": True, "neighborhood_ids": ["9", "15"], "sort_order": "maior_valor", "reference_code": "HE-1", "page": 2}
    result = helenaimoveis.execute("search", filters)
    query = parse_qs(urlsplit(str(requests[0].url)).query)
    assert query["vmi"] == ["1000"] and query["vma"] == ["2500"]
    assert query["areaMinima"] == ["40"] and query["areaMaxima"] == ["100"]
    assert query["dormitorios"] == ["22"] and query["vagas"] == ["21"]
    assert query["bairros"] == ["9,15"] and query["ref"] == ["HE-1"]
    assert result["native"]["items"] == [] and result["display"] == []


def test_canonical_search_route_without_results_marker_is_rejected(monkeypatch):
    body = '<link rel="canonical" href="https://www.helenaimoveis.com.br/imovel/locacao/todos/timoteo/">'
    _mock_responses(monkeypatch, body)
    with pytest.raises(Exception, match="invalid_content"):
        helenaimoveis.execute("search", {})


@pytest.mark.parametrize("arguments", [{}, {"selector": "all"}])
def test_facets_are_rejected_as_unsupported(arguments):
    with pytest.raises(BridgeError, match="unsupported_capability"):
        helenaimoveis.execute("facets", arguments)


def test_unexpected_search_html_is_rejected(monkeypatch):
    _mock_responses(monkeypatch, "<html><title>Unknown</title></html>")
    with pytest.raises(Exception, match="invalid_content"):
        helenaimoveis.execute("search", {})


def test_detail_returns_publicly_serialized_property(monkeypatch):
    body = '<link rel="canonical" href="https://www.helenaimoveis.com.br/imovel/123/casa-locacao"><title>Casa para locação</title><h1 class="info__title">Casa</h1><div id="desc_descricao">Descrição</div>'
    _mock_responses(monkeypatch, body)
    result = helenaimoveis.execute("detail", {"reference": "123"})
    assert result["native"]["overview"]["property_id"] == "123"
    assert result["display"][0]["url"].endswith("/imovel/123")
    _validate_display_reference("helenaimoveis", result["display"][0]["reference"])


def test_generic_detail_html_is_rejected_before_parsing(monkeypatch):
    _mock_responses(monkeypatch, "<article><h1>News</h1><div class='descricao'>Text</div></article>")
    with pytest.raises(Exception, match="invalid_content"):
        helenaimoveis.execute("detail", {"reference": "123"})


def test_spec_closes_filters_and_declares_no_facets():
    spec_path = Path(__file__).resolve().parents[2] / "provider-specs/helenaimoveis.json"
    spec = json.loads(spec_path.read_text())
    assert spec["filters"]["additionalProperties"] is False
    assert spec["facets"] is None
