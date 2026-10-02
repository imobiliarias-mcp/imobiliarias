import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from rental_bridge.errors import BridgeError
from rental_bridge.providers.cabralporto import _display_item, execute


@pytest.fixture(autouse=True)
def provider_specification(monkeypatch):
    from rental_bridge import contracts

    spec_path = Path(__file__).resolve().parents[2] / "provider-specs" / "cabralporto.json"
    monkeypatch.setattr(contracts, "specification", lambda provider: json.loads(spec_path.read_text()))


SEARCH_PAYLOAD = {
    "data": [
        {
            "id": 501,
            "reference": "CP-501",
            "title_formatted": "Apartamento Centro",
            "price": "R$ 2.500",
            "url": "apartamento-centro",
            "address": {"formatted": "Centro - Timóteo/MG"},
            "rooms": {"bedroom": {"value": 2}, "suite": {"value": 1}, "garage": {"value": 1}},
            "areas": {"built_area": {"value": 60, "measure": "m²"}},
        }
    ],
    "meta": {"pagination": {"total": 1, "per_page": 12, "current_page": 2, "total_pages": 1}},
}


def offline_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_search_passes_all_core_criteria_to_tecimob_builder():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=SEARCH_PAYLOAD, request=request)

    client = offline_client(respond)
    result = execute(
        "search",
        {
            "city_slug": "ipatinga-mg",
            "neighborhood_slug": "centro",
            "property_type": "apartamento",
            "bedrooms": 2,
            "min_bedrooms": False,
            "suites": 1,
            "garages": 1,
            "min_price": 1000,
            "max_price": 4000,
            "min_area": 40,
            "max_area": 100,
            "area_type": "built_area",
            "page": 2,
            "limit": 12,
            "sort": "price",
        },
        client=client,
    )

    request = requests[0]
    parameters = parse_qs(request.url.query.decode())
    assert request.headers["x-domain"] == "cabralportoimoveis.com.br"
    assert parameters["filter[by_neighborhood_or_city_slug]"] == ["ipatinga-mg"]
    assert parameters["filter[by_neighborhood_slug]"] == ["centro"]
    assert parameters["filter[by_type_or_subtype_slug]"] == ["apartamento"]
    assert parameters["filter[by_room_equals][bedroom]"] == ["2"]
    assert parameters["filter[by_room_greater_equals][suite]"] == ["1"]
    assert parameters["filter[by_room_greater_equals][garage]"] == ["1"]
    assert parameters["filter[by_higher_than_price]"] == ["1000"]
    assert parameters["filter[by_lower_than_price]"] == ["4000"]
    assert parameters["filter[by_area][greater_equals]"] == ["40"]
    assert parameters["filter[by_area][lower_equals]"] == ["100"]
    assert parameters["filter[by_area][name]"] == ["built_area"]
    assert parameters["offset"] == ["2"]
    assert parameters["limit"] == ["12"]
    assert parameters["sort"] == ["price"]
    assert result["native"]["listings"][0]["reference"] == "CP-501"
    assert result["display"][0]["reference"] == "CP-501"
    assert result["display"][0]["url"] == "https://cabralportoimoveis.com.br/imovel/apartamento-centro"
    json.dumps(result)
    client.close()


def test_display_omits_unknown_fields_but_preserves_zero_price():
    item = {
        "reference": "",
        "url": "https://cabralportoimoveis.com.br/imovel/apartamento-501",
        "title": "",
        "formatted_address": "",
        "price": 0,
    }

    assert _display_item(item) == {"url": item["url"], "price": 0}


def test_detail_returns_explicit_native_detail_and_display_fields():
    payload = {"data": {"id": 501, "reference": "CP-501", "url": "apartamento-centro", "title_formatted": "Apartamento Centro", "price": "R$ 2.500", "address": {"formatted": "Centro - Timóteo/MG"}, "rooms": {}, "areas": {}, "images_extra": []}}

    def respond(request):
        return httpx.Response(200, json=payload, request=request)

    client = offline_client(respond)
    result = execute("detail", {"reference": "CP-501"}, client=client)

    assert result["native"]["reference"] == "CP-501"
    assert result["native"]["canonical_url"] == "https://cabralportoimoveis.com.br/imovel/apartamento-centro"
    assert result["display"][0]["reference"] == "CP-501"
    assert result["display"][0]["url"] == result["native"]["canonical_url"]
    json.dumps(result)
    client.close()


def test_search_preserves_multiple_valid_results():
    second_item = {
        "id": 502,
        "reference": "CP-502",
        "title_formatted": "Casa Centro",
        "price": "R$ 3.000",
        "url": "casa-centro",
        "address": {"formatted": "Centro - Timóteo/MG"},
        "rooms": {},
        "areas": {},
    }
    payload = {"data": [SEARCH_PAYLOAD["data"][0], second_item], "meta": SEARCH_PAYLOAD["meta"]}

    def respond(request):
        return httpx.Response(200, json=payload, request=request)

    result = execute("search", {}, client=offline_client(respond))

    assert [item["reference"] for item in result["display"]] == ["CP-501", "CP-502"]


def test_search_accepts_a_valid_empty_result_page():
    def respond(request):
        return httpx.Response(200, json={"data": [], "meta": {"pagination": {"total": 0, "per_page": 12, "current_page": 1, "total_pages": 0}}}, request=request)

    result = execute("search", {}, client=offline_client(respond))

    assert result["native"]["listings"] == []
    assert result["native"]["total_count"] == 0
    assert result["display"] == []


def test_search_rejects_unrelated_json_object():
    def respond(request):
        return httpx.Response(200, json={}, request=request)

    with pytest.raises(BridgeError, match="invalid_content"):
        execute("search", {}, client=offline_client(respond))


@pytest.mark.parametrize(("status", "code"), [(403, "blocked"), (429, "rate_limited"), (500, "http_error")])
def test_search_rejects_http_failures_before_parsing(status, code):
    def respond(request):
        return httpx.Response(status, json={}, request=request)

    with pytest.raises(BridgeError) as error:
        execute("search", {}, client=offline_client(respond))

    assert error.value.code == code


def test_facets_cities_selector_matches_native_collection_key():
    def respond(request):
        if request.url.path.endswith("/filters/states"):
            data = [{"acronym": "MG", "cities": [{"id": 7, "name": "Timóteo"}]}]
        else:
            data = []
        return httpx.Response(200, json={"data": data}, request=request)

    result = execute("facets", {"selector": "cities"}, client=offline_client(respond))

    assert result["native"] == {"cities": [{"id": "7", "name": "Timóteo", "state": "MG"}]}


def test_facets_types_selector_matches_native_collection_key():
    def respond(request):
        data = []
        if request.url.path.endswith("/filters/types"):
            data = [{"id": 3, "title": "Apartamento", "symbol": "house"}]
        if request.url.path.endswith("/filters/states"):
            data = [{"acronym": "MG", "cities": []}]
        return httpx.Response(200, json={"data": data}, request=request)

    result = execute("facets", {"selector": "types"}, client=offline_client(respond))

    assert result["native"] == {"types": [{"id": "3", "title": "Apartamento", "symbol": "house"}]}


def test_facets_honors_requested_selector():
    def respond(request):
        if request.url.path.endswith("filters/states"):
            data = {"data": [{"acronym": "MG", "cities": [{"id": 1, "name": "Timóteo"}]}]}
        elif request.url.path.endswith("filters/neighborhoods"):
            data = {"data": [{"id": 7, "name": "Centro"}]}
        else:
            data = {"data": [{"id": 3, "title": "Apartamento"}]}
        return httpx.Response(200, json=data, request=request)

    client = offline_client(respond)
    result = execute("facets", {"selector": "neighborhoods"}, client=client)

    assert result["native"] == {"neighborhoods": [{"id": "7", "name": "Centro"}]}
    assert result["display"] == []
    client.close()
