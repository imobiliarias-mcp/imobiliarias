import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from rental_bridge.errors import BridgeError
from rental_bridge.providers.arthusoimoveis import _display_item, execute


@pytest.fixture(autouse=True)
def provider_specification(monkeypatch):
    from rental_bridge import contracts

    spec_path = Path(__file__).resolve().parents[2] / "provider-specs" / "arthusoimoveis.json"
    monkeypatch.setattr(contracts, "specification", lambda provider: json.loads(spec_path.read_text()))


SEARCH_HTML = '''
<div class="item-listing-wrap" data-listid="42">
  <h2 class="item-title"><a href="/property/apartamento-centro/">Apartamento Centro</a></h2>
  <span class="item-price">R$ 2.400</span>
  <div class="h-beds"><span class="hz-figure">2</span></div>
  <div class="h-baths"><span class="hz-figure">1</span></div>
  <div class="h-type"><span>Apartamento</span></div>
</div>
'''


def offline_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_uses_every_supported_query_field():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, text=SEARCH_HTML, headers={"content-type": "text/html"}, request=request)

    client = offline_client(respond)
    result = execute(
        "search",
        {
            "city": "timoteo",
            "neighborhood": "centro",
            "property_type": "apartamento",
            "bedrooms": 2,
            "bathrooms": 1,
            "min_price": 1200,
            "max_price": 3000,
            "property_code": "A-42",
            "keyword": "Centro",
            "sort_by": "a_price",
            "page": 2,
        },
        client=client,
    )

    request = requests[0]
    parameters = parse_qs(request.url.query.decode())
    assert request.url.path == "/busca/page/2/"
    assert parameters["status[0]"] == ["alugar"]
    assert parameters["location[0]"] == ["timoteo"]
    assert parameters["areas[0]"] == ["centro"]
    assert parameters["type[0]"] == ["apartamento"]
    assert parameters["bedrooms"] == ["2"]
    assert parameters["bathrooms"] == ["1"]
    assert parameters["min-price"] == ["1200"]
    assert parameters["max-price"] == ["3000"]
    assert parameters["property_id"] == ["A-42"]
    assert parameters["keyword"] == ["Centro"]
    assert parameters["sortby"] == ["a_price"]
    assert result["native"]["items"][0]["post_id"] == 42
    assert result["display"][0]["reference"] == {"kind": "id", "value": "42"}
    assert result["display"][0]["title"] == "Apartamento Centro"
    assert result["display"][0]["url"] == "https://arthusoimoveis.com.br/property/apartamento-centro/"
    json.dumps(result)
    client.close()


def test_display_omits_unknown_fields_but_preserves_zero_price():
    item = {
        "post_id": None,
        "slug": "",
        "url": "https://arthusoimoveis.com.br/property/imovel-501/",
        "title": "",
        "price_text": 0,
    }

    assert _display_item(item) == {"url": item["url"], "price": 0}


def test_detail_serializes_explicit_typed_public_fields():
    payload = {
        "id": 42,
        "slug": "apartamento-centro",
        "link": "https://arthusoimoveis.com.br/property/apartamento-centro/",
        "title": {"rendered": "Apartamento Centro"},
        "content": {"rendered": "Descrição"},
        "property_meta": {"fave_property_id": ["A-42"]},
        "_embedded": {"wp:term": []},
    }

    def respond(request):
        return httpx.Response(200, json=payload, request=request)

    client = offline_client(respond)
    result = execute("detail", {"reference": {"kind": "id", "value": "42"}}, client=client)

    assert result["native"]["summary"]["title"] == "Apartamento Centro"
    assert result["native"]["description"] == "Descrição"
    assert not any(key.startswith("_") for key in result["native"])
    assert result["display"][0]["reference"] == {"kind": "id", "value": "42"}
    json.dumps(result)
    client.close()


def test_search_preserves_multiple_listing_references():
    second_listing = SEARCH_HTML.replace('data-listid="42"', 'data-listid="43"').replace(
        "/property/apartamento-centro/", "/property/casa-centro/"
    )

    def respond(request):
        return httpx.Response(200, text=SEARCH_HTML + second_listing, headers={"content-type": "text/html"}, request=request)

    result = execute("search", {}, client=offline_client(respond))

    assert [item["reference"] for item in result["display"]] == [
        {"kind": "id", "value": "42"},
        {"kind": "id", "value": "43"},
    ]


def test_search_uses_slug_reference_when_card_has_no_numeric_id():
    card = SEARCH_HTML.replace(' data-listid="42"', "")

    def respond(request):
        return httpx.Response(200, text=card, headers={"content-type": "text/html"}, request=request)

    result = execute("search", {}, client=offline_client(respond))

    assert result["display"][0]["reference"] == {"kind": "slug", "value": "apartamento-centro"}


@pytest.mark.parametrize("body", ["<html><body>Maintenance</body></html>", "<html><body>Gateway ready</body></html>"])
def test_search_rejects_unrelated_html(body):
    def respond(request):
        return httpx.Response(200, text=body, headers={"content-type": "text/html"}, request=request)

    with pytest.raises(BridgeError, match="invalid_content"):
        execute("search", {}, client=offline_client(respond))


def test_search_accepts_valid_empty_result_container():
    body = '<div class="listing-view list-view card-deck"></div>'

    def respond(request):
        return httpx.Response(200, text=body, headers={"content-type": "text/html"}, request=request)

    result = execute("search", {}, client=offline_client(respond))

    assert result["native"]["items"] == []
    assert result["native"]["returned_count"] == 0


def test_detail_rejects_unrelated_json_object():
    def respond(request):
        return httpx.Response(200, json={}, request=request)

    with pytest.raises(BridgeError, match="invalid_content"):
        execute("detail", {"reference": {"kind": "id", "value": "42"}}, client=offline_client(respond))


def test_facets_accepts_empty_taxonomy_list():
    def respond(request):
        return httpx.Response(200, json=[], request=request)

    result = execute("facets", {"selector": "cities"}, client=offline_client(respond))

    assert result["native"] == {"cities": []}


def test_facets_rejects_non_taxonomy_json_object():
    def respond(request):
        return httpx.Response(200, json={}, request=request)

    with pytest.raises(BridgeError, match="invalid_content"):
        execute("facets", {"selector": "cities"}, client=offline_client(respond))


@pytest.mark.parametrize(("status", "code"), [(403, "blocked"), (429, "rate_limited"), (500, "http_error")])
def test_search_rejects_http_failures_before_parsing(status, code):
    def respond(request):
        return httpx.Response(status, text="upstream error", request=request)

    with pytest.raises(BridgeError) as error:
        execute("search", {}, client=offline_client(respond))

    assert error.value.code == code


def test_facets_selects_a_single_taxonomy():
    def respond(request):
        if request.url.path.endswith("property_city"):
            values = [{"id": 1, "name": "Timóteo", "slug": "timoteo", "count": 5}]
        else:
            values = []
        return httpx.Response(200, json=values, request=request)

    client = offline_client(respond)
    result = execute("facets", {"selector": "cities"}, client=client)

    assert result["native"] == {"cities": [{"term_id": 1, "name": "Timóteo", "slug": "timoteo", "count": 5}]}
    assert result["display"] == []
    client.close()
