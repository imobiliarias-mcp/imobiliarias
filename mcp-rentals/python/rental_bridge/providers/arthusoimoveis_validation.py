"""Argument validation for the Arthuso bridge boundary."""

import re
from typing import Any

SEARCH_ARGUMENTS = {
    "city", "neighborhood", "property_type", "bedrooms", "bathrooms",
    "min_price", "max_price", "property_code", "keyword", "sort_by", "page",
}
FACET_SELECTORS = {"all", "cities", "neighborhoods", "property_types"}


def validate(operation: str, arguments: dict[str, Any]) -> None:
    if operation not in {"search", "detail", "facets"}:
        raise ValueError(f"Unsupported operation: {operation}")
    _require_arguments_object(arguments)
    _validate_operation_arguments(operation, arguments)
    _reject_unknown_arguments(operation, arguments)


def _require_arguments_object(arguments: Any) -> None:
    if not isinstance(arguments, dict):
        raise TypeError("arguments must be an object")


def _validate_operation_arguments(operation: str, arguments: dict[str, Any]) -> None:
    if operation == "detail":
        _validate_reference(arguments.get("reference"))
    if operation == "facets" and arguments.get("selector") not in FACET_SELECTORS:
        raise ValueError("Unsupported or missing facets selector")


def _validate_reference(reference: Any) -> None:
    if not isinstance(reference, dict) or set(reference) != {"kind", "value"}:
        raise ValueError("detail reference requires kind and value")
    if reference["kind"] not in {"id", "slug"} or not _is_nonempty_string(reference["value"]):
        raise ValueError("detail requires a valid typed reference")
    _validate_reference_value(reference)


def _validate_reference_value(reference: dict[str, str]) -> None:
    if reference["kind"] == "id" and not reference["value"].isdigit():
        raise ValueError("id references must contain digits only")
    if reference["kind"] == "slug" and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", reference["value"]):
        raise ValueError("slug reference contains unsupported characters")


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _reject_unknown_arguments(operation: str, arguments: dict[str, Any]) -> None:
    allowed = _allowed_arguments(operation)
    unknown = set(arguments) - allowed
    if unknown:
        raise ValueError(f"Unsupported arguments: {sorted(unknown)}")


def _allowed_arguments(operation: str) -> set[str]:
    if operation == "search":
        return SEARCH_ARGUMENTS
    if operation == "detail":
        return {"reference"}
    return {"selector"}
