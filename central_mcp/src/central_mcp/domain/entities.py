"""Domain entities adhering to Object Calisthenics principles."""

from dataclasses import dataclass
from typing import Any

from central_mcp.domain.value_objects import (
    BedroomsCount,
    ListingPrice,
    ProviderId,
    PublicUrl,
)


@dataclass(frozen=True)
class ListingIdentity:
    """Combines property identifier and canonical web link."""

    property_id: str
    url: PublicUrl


@dataclass(frozen=True)
class ListingLocation:
    """Geographic placement of a listing."""

    neighborhood: str
    city: str


@dataclass(frozen=True)
class ListingFeatures:
    """Core physical and monetary properties of a listing."""

    price: ListingPrice
    bedrooms: BedroomsCount


@dataclass(frozen=True)
class ListingSummary:
    """Aggregated summary representation for search results."""

    identity: ListingIdentity
    features: ListingFeatures
    location: ListingLocation
    title: str
    provider: ProviderId
    bathrooms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize listing summary to dictionary."""
        return {
            "id": self.identity.property_id,
            "title": self.title,
            "price": self.features.price.formatted(),
            "price_numeric": self.features.price.amount,
            "bedrooms": self.features.bedrooms.count,
            "bathrooms": self.bathrooms,
            "neighborhood": self.location.neighborhood,
            "city": self.location.city,
            "url": str(self.identity.url),
            "provider": self.provider.value,
        }


@dataclass(frozen=True)
class PropertyDetail:
    """Complete specifications and media gallery for a property."""

    summary: ListingSummary
    description: str
    photos: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize complete detail to dictionary."""
        data = self.summary.to_dict()
        data["description"] = self.description
        data["photos"] = list(self.photos)
        return data


@dataclass(frozen=True)
class ProviderSpec:
    """Metadata specification describing a rental provider."""

    identifier: ProviderId
    coverage_region: str
    supported_operations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize provider spec to dictionary."""
        return {
            "provider_name": self.identifier.value,
            "coverage_region": self.coverage_region,
            "supported_operations": list(self.supported_operations),
        }
