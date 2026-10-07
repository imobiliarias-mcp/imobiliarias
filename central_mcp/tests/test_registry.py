"""Unit tests for ProviderRegistry."""

import pytest
from central_mcp.providers.registry import ProviderRegistry


def test_registry_contains_all_15_providers():
    """Verify registry knows about all 15 rental providers."""
    registry = ProviderRegistry.create_default()
    assert len(registry.all_provider_ids()) == 15
    assert "cabralporto" in registry.all_provider_ids()
    assert "vivareal" in registry.all_provider_ids()
    assert "casalinhares" in registry.all_provider_ids()
    assert "epifanioimoveis" in registry.all_provider_ids()


def test_registry_catalog():
    """Verify catalog method produces structured provider specs."""
    registry = ProviderRegistry.create_default()
    cat = registry.catalog()
    assert len(cat) == 15
    cabral = cat.get("cabralporto")
    assert cabral is not None
    assert cabral.identifier.value == "cabralporto"


def test_registry_get_valid_provider():
    """Verify registry retrieves registered adapter."""
    registry = ProviderRegistry.create_default()
    adapter = registry.get("cabralporto")
    assert hasattr(adapter, "search_rentals")
    assert hasattr(adapter, "get_property_detail")
    assert hasattr(adapter, "get_facets")
    assert hasattr(adapter, "get_provider_info")


def test_registry_get_unknown_provider():
    """Verify registry raises KeyError on unknown provider."""
    registry = ProviderRegistry.create_default()
    with pytest.raises(KeyError):
        registry.get("unknown_agency_xyz")
