"""Offline contract tests for the Vale Invest adapter."""
import json
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from jsonschema import Draft202012Validator, ValidationError

from rental_bridge.errors import BridgeError
from rental_bridge.providers import imobiliariavaleinvest

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

    monkeypatch.setattr(imobiliariavaleinvest, "managed_httpx", managed_client)
    return requests


def test_search_uses_real_path_builder_and_composed_filters(monkeypatch):
    body = '<input id="countResultado" type="hidden" value="0"><div id="lista" class="todos_imoveis"></div>'
    requests = _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    filters = {"city": "Timóteo", "neighborhood": "Centro", "property_type": "apartamento", "minimum_bedrooms": 2, "minimum_price": 1000, "maximum_price": 2500, "sort_field": "valor", "sort_direction": "decrescente", "page": 2, "page_size": 20}
    result = imobiliariavaleinvest.execute("search", filters)
    path = urlsplit(str(requests[0].url)).path
    assert "/alugar/mg/timoteo/centro/apartamento/dormitorios-2/" in path
    assert "valor-1000_2500" in path and "quantidade-20/pagina-2" in path
    assert result["native"]["listings"] == [] and result["display"] == []


def test_detail_fetches_only_validated_public_card_url(monkeypatch):
    url = "https://imobiliariavaleinvest.com.br/alugar/mg/timoteo/centro/casa/123"
    body = f'<input id="pkimovel_ficha" value="123"><input id="referencia_imovel_ficha" value="REF123"><link rel="canonical" href="{url}"><h1 class="titulo">Casa</h1>'
    requests = _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    result = imobiliariavaleinvest.execute("detail", {"reference": url})
    assert str(requests[0].url) == url and result["native"]["code"] == "REF123"
    assert result["display"][0]["reference"] == url
    assert result["display"][0]["url"] == result["native"]["url"]
    _validate_display_reference("imobiliariavaleinvest", result["display"][0]["reference"])


def test_search_display_reference_matches_public_card_schema(monkeypatch):
    body = '<a class="link_resultado" href="/alugar/mg/timoteo/centro/casa/123"><span class="titulo_novo">Casa</span><span class="final_card">Centro, Timóteo</span><h5>R$ 1.200,00</h5></a>'
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    result = imobiliariavaleinvest.execute("search", {})
    _validate_display_reference("imobiliariavaleinvest", result["display"][0]["reference"])
    assert result["display"][0]["reference"] == result["native"]["listings"][0]["url"]


def test_detail_rejects_arbitrary_hosts_before_request(monkeypatch):
    requests = _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=""))
    with pytest.raises(BridgeError, match="invalid_input"):
        imobiliariavaleinvest.execute("detail", {"reference": "https://127.0.0.1/imovel/123"})
    assert requests == []


def test_detail_rejects_non_card_routes_before_request(monkeypatch):
    requests = _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=""))
    reference = "https://imobiliariavaleinvest.com.br/alugar/mg/timoteo/centro/imovel/123"
    with pytest.raises(BridgeError, match="invalid_input"):
        imobiliariavaleinvest.execute("detail", {"reference": reference})
    assert requests == []


def test_unexpected_search_html_is_rejected(monkeypatch):
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text="<html><title>Unknown</title></html>"))
    with pytest.raises(Exception, match="invalid_content"):
        imobiliariavaleinvest.execute("search", {})


def test_nonzero_count_without_listing_identity_is_rejected(monkeypatch):
    body = '<input id="countResultado" type="hidden" value="12"><div id="lista" class="todos_imoveis"></div>'
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    with pytest.raises(Exception, match="invalid_content"):
        imobiliariavaleinvest.execute("search", {})


def test_unknown_detail_page_is_rejected_before_parsing(monkeypatch):
    url = "https://imobiliariavaleinvest.com.br/alugar/mg/timoteo/centro/casa/123"
    _mock_responses(monkeypatch, lambda request: httpx.Response(200, text="<html><title>Unknown</title></html>"))
    with pytest.raises(Exception, match="invalid_content"):
        imobiliariavaleinvest.execute("detail", {"reference": url})


@pytest.mark.parametrize(
    ("filters", "expected_segments"),
    [
        ({"sort_field": "bairro"}, ("ordem-bairro", "resultado-crescente")),
        ({"sort_direction": "decrescente"}, ("ordem-valor", "resultado-decrescente")),
    ],
)
def test_partial_sort_filters_use_source_default(monkeypatch, filters, expected_segments):
    body = '<input id="countResultado" value="0"><div id="lista" class="todos_imoveis"></div>'
    requests = _mock_responses(monkeypatch, lambda request: httpx.Response(200, text=body))
    imobiliariavaleinvest.execute("search", filters)
    path = urlsplit(str(requests[0].url)).path
    assert all(segment in path for segment in expected_segments)


def test_facets_require_explicit_all_selector(monkeypatch):
    requests = _mock_responses(monkeypatch, lambda request: httpx.Response(200, json={"imoveis": []}))
    with pytest.raises(BridgeError, match="invalid_input"):
        imobiliariavaleinvest.execute("facets", {})
    result = imobiliariavaleinvest.execute("facets", {"selector": "all"})
    assert result["native"] == {"cities": (), "neighborhoods": (), "types": ()}
    assert len(requests) == 1


def test_spec_declares_effective_filters_and_detail_route():
    spec_path = Path(__file__).resolve().parents[2] / "provider-specs/imobiliariavaleinvest.json"
    spec = json.loads(spec_path.read_text())
    assert spec["filters"]["additionalProperties"] is False
    assert {"minimum_price", "maximum_price", "minimum_bedrooms", "sort_field", "sort_direction", "page_size"} <= set(spec["filters"]["properties"])
    assert spec["facets"]["properties"]["selector"]["const"] == "all"
    assert "/imovel/" not in spec["reference"]["pattern"]
    Draft202012Validator(spec["reference"]).validate(
        "https://imobiliariavaleinvest.com.br/alugar/mg/timoteo/centro/casa/123"
    )
    with pytest.raises(ValidationError):
        Draft202012Validator(spec["reference"]).validate(
            "https://imobiliariavaleinvest.com.br/alugar/mg/timoteo/centro/imovel/123"
        )
