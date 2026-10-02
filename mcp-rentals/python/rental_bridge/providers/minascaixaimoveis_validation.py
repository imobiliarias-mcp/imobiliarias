"""Validate Minas Caixa operations before their source service is invoked."""

from typing import Any

from rental_bridge.errors import BridgeError


def validate_arguments(operation: str, arguments: dict[str, Any]) -> None:
    if operation not in {"search", "detail", "facets"} or not isinstance(arguments, dict):
        raise BridgeError("invalid_input")
    if operation == "detail":
        _validate_detail(arguments)
        return
    if operation == "facets":
        _validate_facets(arguments)
        return
    _validate_search(arguments)


def _validate_search(arguments: dict[str, Any]) -> None:
    allowed = {"city", "bedrooms", "parking_spaces", "min_price", "max_price", "sort", "page"}
    if set(arguments) - allowed:
        raise BridgeError("invalid_input")
    _validate_price_range(arguments)


def _validate_detail(arguments: dict[str, Any]) -> None:
    reference = arguments.get("reference")
    if not isinstance(reference, str) or not reference.isdigit() or int(reference) < 1:
        raise BridgeError("invalid_input")
    if set(arguments) != {"reference"}:
        raise BridgeError("invalid_input")


def _validate_facets(arguments: dict[str, Any]) -> None:
    selector = arguments.get("selector")
    if selector not in {"cities", "neighborhoods"}:
        raise BridgeError("invalid_input")
    _validate_facet_arguments(arguments, selector)


def _validate_facet_arguments(arguments: dict[str, Any], selector: str) -> None:
    if set(arguments) - {"selector", "city"}:
        raise BridgeError("invalid_input")
    if selector == "cities" and "city" in arguments:
        raise BridgeError("invalid_input")
    if selector == "neighborhoods" and not arguments.get("city", "").strip():
        raise BridgeError("invalid_input")


def _validate_price_range(arguments: dict[str, Any]) -> None:
    minimum = arguments.get("min_price")
    maximum = arguments.get("max_price")
    if minimum is not None and maximum is not None and maximum > 0 and minimum > maximum:
        raise BridgeError("invalid_input")
