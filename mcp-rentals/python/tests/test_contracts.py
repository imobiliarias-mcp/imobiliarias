"""Cross-language boundary rules applied before any provider imports."""
import pytest

from rental_bridge.contracts import validate_public_url, validate_request
from rental_bridge.errors import BridgeError


def test_unknown_provider_and_filters_are_rejected():
    with pytest.raises(BridgeError, match='invalid_input'):
        validate_request({'version': 1, 'provider': 'unknown', 'operation': 'search', 'arguments': {}})
    with pytest.raises(BridgeError, match='invalid_input'):
        validate_request({'version': 1, 'provider': 'imovelweb', 'operation': 'search', 'arguments': {'minimum_price': 5}})


def test_vivareal_rejects_cross_field_pagination_before_execution():
    for arguments in [{'page': 2, 'offset': 30}, {'offset': 1, 'size': 30}]:
        with pytest.raises(BridgeError, match='invalid_input'):
            validate_request({'version': 1, 'provider': 'vivareal', 'operation': 'search', 'arguments': arguments})


def test_typed_id_does_not_accept_a_slug():
    with pytest.raises(BridgeError, match='invalid_input'):
        validate_request({'version': 1, 'provider': 'arthusoimoveis', 'operation': 'detail', 'arguments': {'reference': {'kind': 'id', 'value': 'apartamento-centro'}}})


def test_neighborhoods_require_city_and_helena_has_no_facets():
    with pytest.raises(BridgeError, match='invalid_input'):
        validate_request({'version': 1, 'provider': 'veraimobiliaria', 'operation': 'facets', 'arguments': {'selector': 'neighborhoods'}})
    with pytest.raises(BridgeError, match='unsupported_capability'):
        validate_request({'version': 1, 'provider': 'helenaimoveis', 'operation': 'facets', 'arguments': {'selector': 'all'}})


@pytest.mark.parametrize('url', ['http://127.0.0.1/imovel/x', 'https://www.vivareal.com.br/api/x', 'https://www.vivareal.com.br/imovel/%2e%2e/api', 'https://name:pass@www.vivareal.com.br/imovel/x'])
def test_url_detail_is_not_an_arbitrary_fetch(url):
    with pytest.raises(BridgeError, match='invalid_input'):
        validate_public_url(url, 'vivareal')
