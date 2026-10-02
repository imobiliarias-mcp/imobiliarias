import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from _provider_contract_assertions import assert_worker_response

from rental_bridge import contracts
from rental_bridge.errors import BridgeError
from rental_bridge.providers.marcioimoveis import execute

ROOT = Path(__file__).resolve().parents[3]
SEARCH_PAGE = '''
<div class="rh_pagination__stats" data-page="2" data-max="5" data-total-properties="42"></div>
<article class="rh_prop_card post-608">
  <h3><a href="/imovel/apartamento-santa-terezinha/">Apartamento Santa Terezinha</a></h3>
  <div class="rh_prop_card__price">R$ 1.500,00</div>
  <div class="rh_prop_card__meta">Quartos 2</div>
  <div class="rh_prop_card__meta">Banheiros 1</div>
</article>
'''
DETAIL_PAGE = '''
<h1 class="rh_page__title">Apartamento Santa Terezinha</h1>
<div class="price">R$ 1.500,00</div>
<div class="rh_content">Imóvel para alugar próximo ao centro.</div>
'''
FACETS_PAGE = '''
<script>var realhomesLocationsData = {"all_locations":[{"name":"Timóteo","slug":"timoteo","count":5,"term_id":12,"children":[]}]};</script>
<select name="type[]"><option value="apartamento">Apartamento</option></select>
<select name="status"><option value="alugar">Aluguel</option></select>
'''


def install_contract(monkeypatch):
    specification = json.loads((ROOT / "mcp-rentals/provider-specs/marcioimoveis.json").read_text())
    monkeypatch.setattr(contracts, "load_contracts", lambda: {"version": 1, "providers": [specification]})


def test_search_builds_rental_query_and_serializes_parser_results(monkeypatch):
    install_contract(monkeypatch)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=SEARCH_PAGE, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute(
            "search",
            {
                "locations": ["timoteo"], "property_types": ["casas"], "bedrooms": 2,
                "bathrooms": 1, "min_price": 1200, "max_price": 2500,
                "sort": "price-asc", "keyword": "centro", "page": 2,
            },
            client=client,
        )

    assert len(requests) == 1
    assert_worker_response("marcioimoveis", result)
    query = parse_qs(urlsplit(str(requests[0].url)).query)
    assert query["status"] == ["alugar"]
    assert query["location[]"] == ["timoteo"]
    assert query["type[]"] == ["casas"]
    assert query["bedrooms"] == ["2"]
    assert query["bathrooms"] == ["1"]
    assert query["min-price"] == ["1200"]
    assert query["max-price"] == ["2500"]
    assert query["sort-properties"] == ["price-asc"]
    assert query["keyword"] == ["centro"]
    assert str(requests[0].url).startswith("https://marcioimoveis.net.br/properties-search/page/2/")
    assert result["native"]["listings"][0]["property_code"] == "RH-608"
    assert result["display"][0]["reference"] == "https://marcioimoveis.net.br/imovel/apartamento-santa-terezinha/"
    assert result["display"][0]["url"] == result["display"][0]["reference"]
    json.dumps(result, allow_nan=False)


def test_detail_requires_a_validated_public_property_url(monkeypatch):
    install_contract(monkeypatch)
    requests = []
    reference = "https://marcioimoveis.net.br/propriedade/apartamento-santa-terezinha/"

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=DETAIL_PAGE, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("detail", {"reference": reference}, client=client)

    assert len(requests) == 1
    assert_worker_response("marcioimoveis", result)
    assert str(requests[0].url) == reference
    assert result["native"]["url"] == reference
    assert result["display"][0]["url"] == reference
    assert result["display"][0]["reference"] == reference
    assert result["display"][0]["title"] == "Apartamento Santa Terezinha"
    json.dumps(result, allow_nan=False)


def test_numeric_detail_reference_is_not_resolved_by_search_or_fallback(monkeypatch):
    install_contract(monkeypatch)
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=SEARCH_PAGE, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client, pytest.raises(
        BridgeError
    ) as error:
        execute("detail", {"reference": "608"}, client=client)

    assert error.value.code == "invalid_input"
    assert requests == []


def test_facets_returns_the_requested_taxonomy_only(monkeypatch):
    install_contract(monkeypatch)

    def respond(request):
        return httpx.Response(200, text=FACETS_PAGE, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("facets", {"selector": "locations"}, client=client)

    assert result["native"]["locations"][0]["slug"] == "timoteo"
    assert set(result["native"]) == {"locations"}
    assert result["display"] == []


def test_explicit_zero_search_results_are_preserved(monkeypatch):
    install_contract(monkeypatch)
    page = '<div class="rh_pagination__stats" data-page="1" data-max="1" data-total-properties="0"></div>'

    def respond(request):
        return httpx.Response(200, text=page, headers={"content-type": "text/html"}, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = execute("search", {}, client=client)

    assert result["native"]["total_properties"] == 0
    assert result["display"] == []


def test_unmarked_html_is_rejected_before_search_parser():
    def respond(request):
        return httpx.Response(200, text="<html><body>Maintenance</body></html>", request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client, pytest.raises(
        BridgeError
    ) as error:
        execute("search", {}, client=client)

    assert error.value.code == "invalid_content"


def test_generic_article_is_not_accepted_as_property_detail(monkeypatch):
    install_contract(monkeypatch)
    generic_article = "<html><article>Maintenance message</article></html>"

    def respond(request):
        return httpx.Response(200, text=generic_article, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client, pytest.raises(
        BridgeError
    ) as error:
        execute(
            "detail",
            {"reference": "https://marcioimoveis.net.br/imovel/teste/"},
            client=client,
        )

    assert error.value.code == "invalid_content"


def test_challenge_document_is_rejected_before_search_parser():
    challenge = '<html><title>Just a moment</title><form id="challenge-form"></form></html>'

    def respond(request):
        return httpx.Response(200, text=challenge, request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client, pytest.raises(
        BridgeError
    ) as error:
        execute("search", {}, client=client)

    assert error.value.code == "blocked"
