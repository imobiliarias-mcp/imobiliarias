"""Argument validation for the Alê Corretora bridge boundary."""

import re
from typing import Any

SEARCH_ARGUMENTS = {
    "city_id", "neighborhood_id", "property_type", "bedrooms", "bathrooms",
    "min_price", "max_price", "code", "page",
}
FACET_SELECTORS = {"all", "cities", "neighborhoods"}


def validate(operation: str, arguments: dict[str, Any]) -> None:
    if operation not in {"search", "detail", "facets"}:
        raise ValueError(f"Unsupported operation: {operation}")
    _require_object(arguments)
    _validate_specific_arguments(operation, arguments)
    _reject_unknown_arguments(operation, arguments)


def _require_object(arguments: Any) -> None:
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be an object")


def _validate_specific_arguments(operation: str, arguments: dict[str, Any]) -> None:
    if operation == "detail" and not _valid_reference(arguments.get("reference")):
        raise ValueError("detail requires a valid reference")
    if operation == "facets" and arguments.get("selector") not in FACET_SELECTORS:
        raise ValueError("Unsupported or missing facets selector")


def _valid_reference(reference: Any) -> bool:
    return isinstance(reference, str) and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", reference))


def _reject_unknown_arguments(operation: str, arguments: dict[str, Any]) -> None:
    unknown = set(arguments) - _allowed_arguments(operation)
    if unknown:
        raise ValueError(f"Unsupported arguments: {sorted(unknown)}")


def _allowed_arguments(operation: str) -> set[str]:
    if operation == "search":
        return SEARCH_ARGUMENTS
    if operation == "detail":
        return {"reference"}
    return {"selector"}
