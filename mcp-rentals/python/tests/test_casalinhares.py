import json
from pathlib import Path

import httpx
import pytest

from rental_bridge.providers.casalinhares import _display_item, execute


@pytest.fixture(autouse=True)
def provider_specification(monkeypatch):
    from rental_bridge import contracts

    spec_path = Path(__file__).resolve().parents[2] / "provider-specs" / "casalinhares.json"
    monkeypatch.setattr(contracts, "specification", lambda provider: json.loads(spec_path.read_text()))


SEARCH_PAYLOAD = {
    "properties": {
        "count": 1,
        "properties": [
            {
                "code": "CL-501",
                "site_title": "Apartamento Centro",
                "rental_value": 2400,
                "property_type": "Apartamento",
                "neighborhood": "Centro",
                "city": "Timóteo",
                "site_url": "https://www.casalinhares.com.br/imovel/apartamento-centro-501",
                "cover_photo": {"url": "https://www.casalinhares.com.br/foto.jpg"},
            }
        ],
    }
}


def offline_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_applies_full_composed_filter_including_cursor():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("/site/database/www.casalinhares.com.br"):
            return httpx.Response(200, json={"database": "tenant-1"}, request=request)
        return httpx.Response(200, json=SEARCH_PAYLOAD, request=request)

    client = offline_client(respond)
    result = execute(
        "search",
        {
            "city": "Timóteo",
            "neighborhood": "Centro",
            "property_type": "Apartamento",
            "bedrooms": 2,
            "min_price": 1000,
            "max_price": 3500,
            "cursor": "next-page-token",
        },
        client=client,
    )

    parameters = dict(requests[1].url.params)
    assert parameters["availability"] == "rent"
    assert parameters["city"] == "Timóteo"
    assert parameters["neighborhood"] == "Centro"
    assert parameters["property_type"] == "Apartamento"
    assert parameters["bedroom_gte"] == "2"
    assert parameters["value_min"] == "1000.0"
    assert parameters["value_max"] == "3500.0"
    assert parameters["cursor"] == "next-page-token"
    assert "page" not in parameters
    assert result["native"]["total_count"] == 1
    assert result["display"][0]["reference"] == "CL-501"
    assert result["display"][0]["price"] == 2400.0
    json.dumps(result)
    client.close()


def test_display_omits_unknown_fields_but_preserves_zero_price():
    item = {
        "code": "",
        "url": "https://www.casalinhares.com.br/imovel/apartamento-501",
        "title": "",
        "location": "",
        "rental_price": 0,
    }

    assert _display_item(item) == {"url": item["url"], "price": 0}


def test_search_page_is_used_without_a_cursor():
    requests = []

    def respond(request):
        requests.append(request)
        payload = {"database": "tenant-1"} if "/site/database/" in request.url.path else SEARCH_PAYLOAD
        return httpx.Response(200, json=payload, request=request)

    client = offline_client(respond)
    execute("search", {"page": 4}, client=client)

    assert dict(requests[1].url.params)["page"] == "4"
    client.close()


def test_search_rejects_simultaneous_page_and_cursor():
    with pytest.raises(ValueError, match="mutually exclusive"):
        execute("search", {"page": 2, "cursor": "next-page-token"}, client=offline_client(lambda request: None))


def test_detail_and_facets_serialize_existing_domain_results():
    def respond(request):
        if "/site/database/" in request.url.path:
            payload = {"database": "tenant-1"}
        elif "/properties/search/fields" in request.url.path:
            payload = {"cities": [{"name": "Timóteo"}], "neighborhoods": [{"name": "Centro"}]}
        else:
            payload = {
                "code": "CL-501",
                "site_title": "Apartamento Centro",
                "rental_value": 2400,
                "site_url": "https://www.casalinhares.com.br/imovel/apartamento-centro-501",
                "description": "Descrição",
                "neighborhood": "Centro",
                "city": "Timóteo",
            }
        return httpx.Response(200, json=payload, request=request)

    client = offline_client(respond)
    detail = execute("detail", {"reference": "CL-501"}, client=client)
    facets = execute("facets", {"selector": "neighborhoods"}, client=client)

    assert detail["native"]["code"] == "CL-501"
    assert detail["native"]["description"] == "Descrição"
    assert detail["display"][0]["reference"] == "CL-501"
    assert facets["native"] == {"neighborhoods": [{"name": "Centro"}]}
    assert facets["display"] == []
    json.dumps(detail)
    json.dumps(facets)
    client.close()
