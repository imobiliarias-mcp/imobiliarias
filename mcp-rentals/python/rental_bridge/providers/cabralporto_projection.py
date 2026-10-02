"""Known-field projection for Cabral Porto display cards."""

from typing import Any


def known_fields(values: dict[str, Any]) -> dict[str, Any]:
    """Omit unknown display values without dropping valid numeric zeroes."""
    return {key: value for key, value in values.items() if value is not None and value != ""}
