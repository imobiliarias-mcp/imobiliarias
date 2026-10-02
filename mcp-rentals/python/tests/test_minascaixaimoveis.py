import json
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from _provider_contract_assertions import assert_worker_response

from rental_bridge import contracts
from rental_bridge.errors import BridgeError
from rental_bridge.providers import minascaixaimoveis
from rental_bridge.providers.minascaixaimoveis import execute

ROOT = Path(__file__).resolve().parents[3]


def install_contract(monkeypatch):
    specification = json.loads((ROOT / "mcp-rentals/provider-specs/minascaixaimoveis.json").read_text())
    monkeypatch.setattr(contracts, "load_contracts", lambda: {"version": 1, "providers": [specification]})


def test_search_posts_criteria_and_serializes_public_property_links(monkeypatch):
    install_contract(monkeypatch)
    requests = []
    payload = {
        "quantidade": 1,
        "lista": [{"codigo": "6161", "titulo": "Prédio Comercial", "valor": "R$ 2.000,00", "cidade": "Timóteo", "bairro": "Centro", "numeroquartos": "2", "areainterna": "90"}],
    }

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute(
            "search", {"city": "timoteo", "bedrooms": 2, "min_price": 1000, "max_price": 3000, "page": 2, "sort": "valordesc"}, client=client
        )

    assert len(requests) == 1
    assert_worker_response("minascaixaimoveis", result)
    form = parse_qs(requests[0].content.decode())
    assert str(requests[0].url) == "https://www.minascaixaimoveis.com.br/imoveis/ajax/"
    assert form["imovel[finalidade]"] == ["aluguel"]
    assert form["imovel[codigocidade]"] == ["timoteo"]
    assert form["imovel[numeroquartos]"] == ["2-quartos"]
    assert form["imovel[valorde]"] == ["1000"]
    assert form["imovel[valorate]"] == ["3000"]
    assert form["imovel[pagina]"] == ["2"]
    assert result["native"]["total_count"] == 1
    assert result["native"]["listings"][0]["url"] == "https://www.minascaixaimoveis.com.br/detalhe-imovel/6161"
    assert result["display"] == [{"reference": "6161", "url": "https://www.minascaixaimoveis.com.br/detalhe-imovel/6161", "title": "Prédio Comercial", "location": "Centro, Timóteo", "price": "R$ 2.000,00"}]
    json.dumps(result, allow_nan=False)


def test_detail_returns_raw_native_attributes_and_public_display(monkeypatch):
    install_contract(monkeypatch)
    detail = {"codigo": 6161, "titulo": "Prédio Comercial", "tipo": "Prédio", "valor": "R$ 2.000,00", "cidade": "Timóteo"}
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"quantidade": 1, "lista": [detail]}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("detail", {"reference": "6161"}, client=client)

    assert len(requests) == 1
    assert_worker_response("minascaixaimoveis", result)
    assert parse_qs(requests[0].content.decode()) == {"codigo": ["6161"], "finalidade": ["aluguel"]}
    assert result["native"] == detail
    assert result["display"][0]["reference"] == "6161"
    assert result["display"][0]["url"] == "https://www.minascaixaimoveis.com.br/detalhe-imovel/6161"
    json.dumps(result, allow_nan=False)


def test_facets_requires_explicit_selector_and_city_for_neighborhoods(monkeypatch):
    install_contract(monkeypatch)

    with pytest.raises(BridgeError) as missing_selector:
        execute("facets", {}, client=httpx.Client(transport=httpx.MockTransport(lambda request: None)))
    assert missing_selector.value.code == "invalid_input"

    with pytest.raises(BridgeError) as missing_city:
        execute("facets", {"selector": "neighborhoods"}, client=httpx.Client(transport=httpx.MockTransport(lambda request: None)))
    assert missing_city.value.code == "invalid_input"


def test_facets_posts_city_for_neighborhoods(monkeypatch):
    install_contract(monkeypatch)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[{"codigo": 7, "nomeOriginal": "Centro"}], request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("facets", {"selector": "neighborhoods", "city": "timoteo"}, client=client)

    assert str(requests[0].url) == "https://www.minascaixaimoveis.com.br/bairroAjax"
    assert parse_qs(requests[0].content.decode()) == {"cidade": ["timoteo"]}
    assert result["native"] == {"neighborhoods": [{"neighborhood_id": 7, "name": "Centro"}]}
    assert result["display"] == []


def test_facets_supports_cities_selector(monkeypatch):
    install_contract(monkeypatch)

    def respond(request):
        return httpx.Response(200, json=[{"codigo": 12, "nomeOriginal": "Timóteo"}], request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("facets", {"selector": "cities"}, client=client)

    assert result["native"] == {"cities": [{"city_id": 12, "name": "Timóteo"}]}


def test_managed_requests_path_rejects_html_success_response(monkeypatch):
    class HtmlResponseSession:
        def __init__(self):
            self.headers = {}

        def post(self, url, data, timeout):
            return httpx.Response(200, text="<html><body>Maintenance</body></html>")

    @contextmanager
    def managed_session():
        yield HtmlResponseSession()

    monkeypatch.setattr(minascaixaimoveis, "managed_requests", managed_session)

    with pytest.raises(BridgeError) as error:
        execute("search", {})

    assert error.value.code == "invalid_content"


def test_explicit_empty_response_is_a_zero_result_not_a_block(monkeypatch):
    install_contract(monkeypatch)

    def respond(request):
        return httpx.Response(200, json={"quantidade": 0, "lista": []}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("search", {}, client=client)

    assert result["native"]["total_count"] == 0
    assert result["display"] == []
