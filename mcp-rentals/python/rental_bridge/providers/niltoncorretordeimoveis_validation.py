"""Boundary validation for Nilton property identifiers."""

import re
from typing import Any


def validate(operation: str, arguments: dict[str, Any]) -> None:
    """Reject invalid operations, keys, and numeric property identifiers."""
    allowed = {
        "search": {"city", "property_type", "neighborhood_ids", "bedrooms", "min_bedrooms", "suites", "min_suites", "bathrooms", "min_bathrooms", "parking_spaces", "min_parking_spaces", "min_price", "max_price", "min_area", "max_area", "sort", "page", "reference_code"},
        "detail": {"reference"}, "facets": {"selector"},
    }
    if operation not in allowed or not isinstance(arguments, dict) or set(arguments) - allowed[operation]:
        raise ValueError("Invalid operation or arguments")
    if operation == "detail" and not _is_property_id(arguments.get("reference")):
        raise ValueError("detail requires a positive numeric property ID")
    if operation == "facets" and arguments.get("selector") != "locations":
        raise ValueError("facets requires the locations selector")


def _is_property_id(reference: Any) -> bool:
    return (
        isinstance(reference, str)
        and len(reference) <= 32
        and re.fullmatch(r"[1-9][0-9]*", reference) is not None
    )
