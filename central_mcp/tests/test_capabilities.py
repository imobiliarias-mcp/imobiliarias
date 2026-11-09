"""Tests for provider capability matrix and request validation."""

import pytest
from central_mcp.errors import ProviderError, ProviderErrorCode
from central_mcp.providers.capabilities import (
    PROVIDER_CAPABILITIES,
    get_provider_capability,
    resolve_city,
    validate_provider_filters,
    validate_search_request,
)


def test_capabilities_imovelweb_unavailable_and_no_price():
    cap = get_provider_capability("imovelweb")
    assert cap.is_available is False
    assert "Browser required" in cap.unavailable_reason
    assert "min_price" not in cap.supported_filters
    assert "max_price" not in cap.supported_filters


def test_capabilities_arthuso_no_min_price_or_property_type():
    cap = get_provider_capability("arthusoimoveis")
    assert "max_price" in cap.supported_filters
    assert "min_price" not in cap.supported_filters
    assert "property_type" not in cap.supported_filters


def test_capabilities_minascaixa_no_property_type():
    cap = get_provider_capability("minascaixaimoveis")
    assert "property_type" not in cap.supported_filters
    assert "min_price" not in cap.supported_filters


def test_validate_provider_filters_rejects_unsupported():
    with pytest.raises(ProviderError) as exc_info:
        validate_provider_filters("imovelweb", {"max_price": 2000.0})
    assert exc_info.value.code == ProviderErrorCode.UNSUPPORTED_FILTER
    assert "imovelweb does not support filter 'max_price'" in exc_info.value.message


def test_validate_provider_filters_vale_invest_min_price_requires_max():
    with pytest.raises(ProviderError) as exc_info:
        validate_provider_filters("imobiliariavaleinvest", {"min_price": 1000.0})
    assert exc_info.value.code == ProviderErrorCode.UNSUPPORTED_FILTER
    assert "requires max_price" in exc_info.value.message


def test_validate_search_request_bounds():
    with pytest.raises(ValueError, match="page must be >= 1"):
        validate_search_request(page=0)

    with pytest.raises(ValueError, match="min_price must be >= 0"):
        validate_search_request(min_price=-10.0)

    with pytest.raises(ValueError, match="min_price cannot exceed max_price"):
        validate_search_request(min_price=2000.0, max_price=1000.0)

    with pytest.raises(ValueError, match="bedrooms must be >= 0"):
        validate_search_request(bedrooms=-1)


def test_validate_search_request_provider_list_limits():
    with pytest.raises(ValueError, match="Duplicate provider"):
        validate_search_request(providers=["alecorretoramg", "alecorretoramg"])

    with pytest.raises(ValueError, match="Unknown provider"):
        validate_search_request(providers=["fake_agency"])

    with pytest.raises(ValueError, match="Maximum 20 providers"):
        validate_search_request(providers=[f"p{i}" for i in range(21)])


def test_validate_search_request_accepts_every_registered_provider_at_once():
    every_provider = sorted(PROVIDER_CAPABILITIES.keys())
    assert len(every_provider) == 16
    validate_search_request(providers=every_provider, known_providers=set(every_provider))


def test_newhouse_declares_the_filters_its_site_supports():
    capability = get_provider_capability("newhouseimobiliaria")
    assert capability.supported_filters == frozenset(
        {"city", "min_price", "max_price", "bedrooms", "property_type", "page"}
    )
    assert capability.default_city == ""


@pytest.mark.parametrize("provider_id", ["epifanioimoveis", "niltoncorretordeimoveis"])
def test_resolve_city_defaults_to_timoteo_for_city_required_providers(provider_id):
    assert resolve_city(provider_id, None) == "Timóteo"
    assert resolve_city(provider_id, "") == "Timóteo"
    assert resolve_city(provider_id, "   ") == "Timóteo"


def test_resolve_city_keeps_explicit_city():
    assert resolve_city("epifanioimoveis", "Ipatinga") == "Ipatinga"


def test_resolve_city_is_empty_for_providers_without_default():
    assert resolve_city("vivareal", None) == ""
