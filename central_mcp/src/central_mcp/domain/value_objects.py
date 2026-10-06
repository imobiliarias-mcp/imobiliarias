"""Domain Value Objects for Central Rental Research MCP."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderId:
    """Unique identifier for a rental provider."""

    value: str

    def __post_init__(self) -> None:
        """Validate provider format."""
        if not re.match(r"^[a-z0-9_]+$", self.value):
            raise ValueError(f"Invalid provider identifier: {self.value}")


@dataclass(frozen=True)
class ListingPrice:
    """Monetary value representing monthly rental price."""

    amount: float

    def __post_init__(self) -> None:
        """Ensure price is not negative."""
        if self.amount < 0.0:
            raise ValueError("Price cannot be negative")

    def formatted(self) -> str:
        """Format price as BRL currency string."""
        return f"R$ {self.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass(frozen=True)
class PropertyCode:
    """Domain property identification code or reference."""

    value: str

    def __post_init__(self) -> None:
        """Ensure code is not empty."""
        if not self.value.strip():
            raise ValueError("Property code cannot be empty")


@dataclass(frozen=True)
class BedroomsCount:
    """Quantity of bedrooms constraint."""

    count: int

    def __post_init__(self) -> None:
        """Ensure room count is not negative."""
        if self.count < 0:
            raise ValueError("Bedrooms count cannot be negative")


@dataclass(frozen=True)
class PageNumber:
    """Positive 1-indexed pagination number."""

    number: int

    def __post_init__(self) -> None:
        """Ensure page is at least 1."""
        if self.number < 1:
            raise ValueError("Page number must be >= 1")


@dataclass(frozen=True)
class PublicUrl:
    """Canonical public URL representation with validated scheme."""

    address: str

    def __post_init__(self) -> None:
        """Ensure address starts with http or https."""
        valid_scheme = self.address.startswith("http://") or self.address.startswith("https://")
        if not valid_scheme:
            raise ValueError(f"Invalid web URL scheme: {self.address}")

    def __str__(self) -> str:
        return self.address
