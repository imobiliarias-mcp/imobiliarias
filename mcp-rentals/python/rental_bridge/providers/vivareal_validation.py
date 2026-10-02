"""Provider-specific validation for Viva Real adapter calls."""

from typing import Any

from rental_bridge.errors import BridgeError


def validate_listing_payload(payload):
    """Require a real listings array, including an explicit array for zero results."""
    search = payload.get('search')
    if not isinstance(search, dict):
        raise BridgeError('invalid_content')
    result = search.get('result')
    if not isinstance(result, dict) or not isinstance(result.get('listings'), list):
        raise BridgeError('invalid_content')


def validate(operation: str, arguments: dict[str, Any]) -> None:
    """Reject unsupported operation arguments before creating source clients."""
    allowed = {
        "search": {"location_id", "city", "state", "property_type", "bedrooms", "bathrooms", "parking_spaces", "min_price", "max_price", "min_area", "max_area", "sort", "page", "size", "offset"},
        "detail": {"reference"}, "facets": {"selector", "query", "size"},
    }
    if operation not in allowed or not isinstance(arguments, dict) or set(arguments) - allowed[operation]:
        raise ValueError("Invalid operation or arguments")
    if operation == "detail" and not arguments.get("reference", "").strip():
        raise ValueError("detail requires a public property URL")
    if operation == "facets" and (arguments.get("selector") != "location_suggestions" or not arguments.get("query", "").strip()):
        raise ValueError("locations facets require selector and query")
