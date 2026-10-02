"""Boundary validation for Nova Imobiliária adapter calls."""

import re
from typing import Any


def validate(operation: str, arguments: dict[str, Any]) -> None:
    """Reject invalid operations, keys, and unsafe Tecimob references."""
    allowed = {
        "search": {"city", "property_type", "min_price", "max_price", "min_area", "max_area", "area_type", "bedrooms", "min_bedrooms", "suites", "min_suites", "garages", "min_garages", "offset", "limit", "sort"},
        "detail": {"reference"}, "facets": {"selector"},
    }
    if operation not in allowed or not isinstance(arguments, dict) or set(arguments) - allowed[operation]:
        raise ValueError("Invalid operation or arguments")
    if operation == "detail" and not _is_reference(arguments.get("reference")):
        raise ValueError("detail requires a Tecimob ID or reference")
    if operation == "facets" and arguments.get("selector") != "locations":
        raise ValueError("facets requires the locations selector")


def _is_reference(reference: Any) -> bool:
    return (
        isinstance(reference, str)
        and len(reference) <= 128
        and re.fullmatch(r"[A-Za-z0-9_-]+", reference) is not None
    )
