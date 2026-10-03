"""Protocol defining the standard rental provider adapter interface."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RentalProviderAdapter(Protocol):
    """Protocol that each agency MCP adapter must satisfy."""

    def search_rentals(
        self,
        city: str = "",
        min_price: float = 0.0,
        max_price: float = 0.0,
        bedrooms: int = 0,
        property_type: str = "",
        page: int = 1,
    ) -> dict[str, Any]:
        """Search rental properties."""
        ...

    def get_property_detail(self, property_code: str) -> dict[str, Any]:
        """Retrieve property detail."""
        ...

    def get_facets(self) -> dict[str, Any]:
        """Retrieve search facets."""
        ...

    def get_provider_info(self) -> dict[str, Any]:
        """Retrieve provider metadata."""
        ...
