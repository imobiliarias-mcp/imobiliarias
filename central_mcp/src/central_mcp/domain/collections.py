"""First-class domain collections adhering to Object Calisthenics."""

from collections.abc import Iterator
from typing import Any

from central_mcp.domain.entities import ListingSummary, ProviderSpec


class ListingCollection:
    """First-class collection encapsulating rental property summaries."""

    def __init__(self, items: list[ListingSummary] | tuple[ListingSummary, ...] | None = None) -> None:
        """Initialize collection with immutable tuple."""
        self._items = tuple(items or ())

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[ListingSummary]:
        return iter(self._items)

    def first(self) -> ListingSummary | None:
        """Return the first item or None if empty."""
        if not self._items:
            return None
        return self._items[0]

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all listings to dictionary list."""
        return [item.to_dict() for item in self._items]


class ProviderCatalog:
    """First-class collection encapsulating registered rental providers."""

    def __init__(self, specs: list[ProviderSpec] | None = None) -> None:
        """Initialize catalog indexed by provider identifier."""
        self._specs = {spec.identifier.value: spec for spec in (specs or [])}

    def __len__(self) -> int:
        return len(self._specs)

    def get(self, provider_id: str) -> ProviderSpec | None:
        """Retrieve spec by provider ID."""
        return self._specs.get(provider_id)

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all registered providers to dictionary list."""
        return [spec.to_dict() for spec in self._specs.values()]


class FacetResult:
    """First-class collection encapsulating search aggregation facets."""

    def __init__(self, facets: dict[str, Any] | None = None) -> None:
        """Initialize facet result dictionary wrapper."""
        self._facets = dict(facets or {})

    def to_dict(self) -> dict[str, Any]:
        """Serialize facets."""
        return dict(self._facets)
