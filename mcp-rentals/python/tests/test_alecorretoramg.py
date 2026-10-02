import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from rental_bridge.providers.alecorretoramg import _display_item, execute


@pytest.fixture(autouse=True)
def provider_specification(monkeypatch):
    from rental_bridge import contracts

    spec_path = Path(__file__).resolve().parents[2] / "provider-specs" / "alecorretoramg.json"
    monkeypatch.setattr(contracts, "specification", lambda provider: json.loads(spec_path.read_text()))


SEARCH_HTML = '''
<div class="jet-listing-grid__item" data-post-id="501">
  <div class="jet-engine-listing-overlay-wrap" data-url="/imoveis/apartamento-501/"></div>
  <h3 class="elementor-heading-title">Alugar</h3>
  <h3 class="elementor-heading-title">Oferta</h3>
  <h3 class="elementor-heading-title">Apartamento</h3>
  <a href="/bairro/centro">Centro</a><a href="/cidade/timoteo">Timóteo</a>
  <div class="jet-listing-dynamic-field__content">R$ 2.000</div>
  <ul><li class="elementor-icon-list-item">2</li></ul>
</div>
'''


def offline_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_applies_every_advertised_filter_and_serializes_cards():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"content": SEARCH_HTML}, request=request)

    client = offline_client(respond)
    result = execute(
        "search",
        {
            "city_id": "12",
            "neighborhood_id": "7",
            "property_type": "8",
            "bedrooms": 2,
            "bathrooms": 1,
            "min_price": 1000,
            "max_price": 3000,
            "code": "A-501",
            "page": 3,
        },
        client=client,
    )

    parameters = parse_qs(requests[0].content.decode())
    assert parameters["query[_tax_query_cidade]"] == ["12"]
    assert parameters["query[_tax_query_bairro]"] == ["7"]
    assert parameters["query[_tax_query_tipo-de-imovel]"] == ["8"]
    assert parameters["query[_meta_query_quartos]"] == ["2"]
    assert parameters["query[_meta_query_banheiros]"] == ["1"]
    assert parameters["query[_meta_query_preco|range]"] == ["1000_3000"]
    assert parameters["query[_meta_query_codigo-do-imovel]"] == ["A-501"]
    assert parameters["paged"] == ["3"]
    assert result["native"]["listings"][0]["property_id"] == "501"
    assert result["display"] == [
        {
            "reference": "501",
            "url": "https://alecorretoramg.com.br/imoveis/apartamento-501/",
            "title": "Apartamento em Centro, Timóteo",
            "location": "Centro, Timóteo",
            "price": "R$ 2.000",
        }
    ]
    json.dumps(result)
    client.close()


def test_display_omits_unknown_fields_but_preserves_zero_price():
    item = {
        "code": "",
        "property_id": "",
        "url": "https://alecorretoramg.com.br/imoveis/imovel-501/",
        "title": "",
        "location": {"neighborhood": "", "city": ""},
        "price_formatted": 0,
    }

    assert _display_item(item) == {"url": item["url"], "price": 0}


def test_detail_serializes_only_explicit_public_fields():
    page = '<h1>Apartamento Centro</h1><div class="elementor-heading-title">Código do Imóvel: A-501</div><div class="jet-listing-dynamic-field">R$ 2.000</div>'

    def respond(request):
        return httpx.Response(200, text=page, headers={"content-type": "text/html"}, request=request)

    client = offline_client(respond)
    result = execute("detail", {"reference": "A-501"}, client=client)

    assert result["native"]["code"] == "A-501"
    assert result["native"]["title"] == "Apartamento Centro"
    assert not any(key.startswith("_") for key in result["native"])
    assert result["display"][0]["reference"] == "A-501"
    assert result["display"][0]["url"] == "https://alecorretoramg.com.br/imoveis/A-501/"
    json.dumps(result)
    client.close()


def test_facets_honors_requested_selector():
    def respond(request):
        entries = [{"id": 12, "name": "Timóteo", "slug": "timoteo"}]
        return httpx.Response(200, json=entries, request=request)

    client = offline_client(respond)
    result = execute("facets", {"selector": "cities"}, client=client)

    assert result["native"] == {"cities": [{"city_id": "12", "name": "Timóteo", "slug": "timoteo"}]}
    assert result["display"] == []
    client.close()
