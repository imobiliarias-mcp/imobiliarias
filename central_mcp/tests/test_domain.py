"""Unit tests for Central MCP domain models and value objects."""

import pytest

from central_mcp.domain.collections import (
    ListingCollection,
)
from central_mcp.domain.entities import (
    ListingSummary,
)
from central_mcp.domain.value_objects import (
    BedroomsCount,
    ListingPrice,
    PageNumber,
    PropertyCode,
    ProviderId,
    PublicUrl,
)


def test_provider_id_validation():
    """Verify ProviderId enforces valid identifier formatting."""
    pid = ProviderId("cabralporto")
    assert pid.value == "cabralporto"
    with pytest.raises(ValueError):
        ProviderId("invalid id with spaces")


def test_listing_price_validation():
    """Verify ListingPrice rejects negative amounts."""
    price = ListingPrice(1500.0)
    assert price.amount == 1500.0
    with pytest.raises(ValueError):
        ListingPrice(-10.0)


def test_property_code_validation():
    """Verify PropertyCode rejects empty identifiers."""
    code = PropertyCode("AP101")
    assert code.value == "AP101"
    with pytest.raises(ValueError):
        PropertyCode("")


def test_bedrooms_count_validation():
    """Verify BedroomsCount rejects negative numbers."""
    rooms = BedroomsCount(2)
    assert rooms.count == 2
    with pytest.raises(ValueError):
        BedroomsCount(-1)


def test_page_number_validation():
    """Verify PageNumber enforces page >= 1."""
    page = PageNumber(1)
    assert page.number == 1
    with pytest.raises(ValueError):
        PageNumber(0)


def test_public_url_validation():
    """Verify PublicUrl validates schemes."""
    url = PublicUrl("https://cabralportoimoveis.com.br/imovel/1")
    assert str(url) == "https://cabralportoimoveis.com.br/imovel/1"
    with pytest.raises(ValueError):
        PublicUrl("ftp://invalid.com")


def test_listing_collection_first_class():
    """Verify ListingCollection wraps listing list as first-class collection."""
    from central_mcp.domain.entities import (
        ListingFeatures,
        ListingIdentity,
        ListingLocation,
    )
    identity = ListingIdentity(property_id="1", url=PublicUrl("https://exemplo.com/1"))
    features = ListingFeatures(price=ListingPrice(1200.0), bedrooms=BedroomsCount(2))
    location = ListingLocation(neighborhood="Centro", city="Timóteo")
    item = ListingSummary(
        identity=identity,
        features=features,
        location=location,
        title="Casa Centro",
        provider=ProviderId("cabralporto"),
        bathrooms=1,
    )
    col = ListingCollection([item])
    assert len(col) == 1
    assert col.first() == item
    dict_repr = col.to_list()
    assert len(dict_repr) == 1
    assert dict_repr[0]["title"] == "Casa Centro"


def test_listing_summary_condo_fee_and_total_price():
    """Verify ListingSummary serialization preserves condo_fee and total_price."""
    from central_mcp.domain.entities import (
        ListingFeatures,
        ListingIdentity,
        ListingLocation,
    )
    identity = ListingIdentity(property_id="2", url=PublicUrl("https://exemplo.com/2"))
    features = ListingFeatures(
        price=ListingPrice(1500.0),
        bedrooms=BedroomsCount(3),
        condo_fee=350.0,
        total_price=1850.0,
    )
    location = ListingLocation(neighborhood="Quitandinha", city="Timóteo")
    item = ListingSummary(
        identity=identity,
        features=features,
        location=location,
        title="Apto Quitandinha",
        provider=ProviderId("cabralporto"),
        bathrooms=2,
    )
    data = item.to_dict()
    assert data["rent_price"] == 1500.0
    assert data["condo_fee"] == 350.0
    assert data["total_price"] == 1850.0


