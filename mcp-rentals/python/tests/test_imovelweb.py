import json
from pathlib import Path

import httpx
import pytest
from _provider_contract_assertions import assert_worker_response

from rental_bridge import contracts
from rental_bridge.errors import BridgeError
from rental_bridge.providers.imovelweb import _display_item, execute

ROOT = Path(__file__).resolve().parents[3]
SEARCH_FIXTURE = ROOT / "imovelweb/tests/fixtures/search_page.html"
DETAIL_FIXTURE = ROOT / "imovelweb/tests/fixtures/detail_page.html"


def install_contract(monkeypatch):
    specification = json.loads((ROOT / "mcp-rentals/provider-specs/imovelweb.json").read_text())
    monkeypatch.setattr(contracts, "load_contracts", lambda: {"version": 1, "providers": [specification]})


def test_search_uses_native_filters_parser_and_public_cards(monkeypatch):
    install_contract(monkeypatch)
    page = SEARCH_FIXTURE.read_text()
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=page, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute(
            "search",
            {"city": "timoteo", "neighborhood": "centro", "property_type": "apartamentos", "bedrooms": 2, "sort": "menor_preco", "page": 3},
            client=client,
        )

    assert str(requests[0].url) == (
        "https://www.imovelweb.com.br/apartamentos-aluguel-centro-timoteo-2-quartos-"
        "ordem-preco-menor-pagina-3.html"
    )
    assert len(requests) == 1
    assert_worker_response("imovelweb", result)
    assert result["native"]["total_count"] == 8
    assert result["native"]["listings"][0]["code"] == "3037421600"
    assert result["display"][0]["reference"] == "3037421600"
    assert result["display"][0]["url"] == (
        "https://www.imovelweb.com.br/propriedades/"
        "casa-para-aluguel-em-recanto-verde-timoteo-3037421600.html"
    )
    json.dumps(result, allow_nan=False)


def test_detail_uses_numeric_property_code_and_source_fixture(monkeypatch):
    install_contract(monkeypatch)
    page = DETAIL_FIXTURE.read_text()
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=page, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("detail", {"reference": "3037421600"}, client=client)

    assert str(requests[0].url) == (
        "https://www.imovelweb.com.br/propriedades/imovel-3037421600.html"
    )
    assert len(requests) == 1
    assert_worker_response("imovelweb", result)
    assert result["native"]["code"] == "3037421600"
    assert result["display"][0]["reference"] == "3037421600"
    json.dumps(result, allow_nan=False)


def test_facets_returns_only_the_requested_source_selector(monkeypatch):
    install_contract(monkeypatch)
    page = SEARCH_FIXTURE.read_text()

    def respond(request):
        return httpx.Response(200, text=page, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("facets", {"selector": "property_types"}, client=client)

    assert set(result["native"]) == {"property_types"}
    assert result["native"]["property_types"][0] == {
        "label": "Todos os Imóveis", "value": "imoveis"
    }
    assert result["display"] == []


def test_explicit_zero_results_are_not_confused_with_a_block_page(monkeypatch):
    install_contract(monkeypatch)
    page = '<html><h1 class="postingsTitle-module__title">0 Imóveis para alugar em Timóteo, MG</h1></html>'

    def respond(request):
        return httpx.Response(200, text=page, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("search", {}, client=client)

    assert result["native"]["total_count"] == 0
    assert result["display"] == []


def test_display_omits_unknown_optional_fields(monkeypatch):
    install_contract(monkeypatch)

    display = _display_item(
        {
            "code": "3037421600",
            "url": "https://www.imovelweb.com.br/propriedades/teste-3037421600.html",
        }
    )

    assert display == {
        "reference": "3037421600",
        "url": "https://www.imovelweb.com.br/propriedades/teste-3037421600.html",
    }


def test_generic_data_id_is_not_accepted_as_an_imovelweb_search_page(monkeypatch):
    install_contract(monkeypatch)
    arbitrary_html = '<html><div data-id="3037421600">Not a posting card</div></html>'

    def respond(request):
        return httpx.Response(200, text=arbitrary_html, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client, pytest.raises(
        BridgeError
    ) as error:
        execute("search", {}, client=client)

    assert error.value.code == "invalid_content"


def test_challenge_document_is_rejected_before_search_parser(monkeypatch):
    install_contract(monkeypatch)
    challenge = '<html><title>Just a moment</title><script src="/cdn-cgi/challenge-platform/x"></script></html>'

    def respond(request):
        return httpx.Response(200, text=challenge, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client, pytest.raises(
        BridgeError
    ) as error:
        execute("search", {}, client=client)

    assert error.value.code == "blocked"


def test_unknown_search_filters_are_rejected_without_network_access():
    with pytest.raises(BridgeError) as error:
        execute("search", {"bathrooms": 2}, client=httpx.Client(transport=httpx.MockTransport(lambda request: None)))

    assert error.value.code == "invalid_input"
