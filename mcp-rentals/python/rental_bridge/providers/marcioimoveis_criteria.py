"""Build Márcio Imóveis rental criteria from bridge search arguments."""

from typing import Any

from marcio_research.domain.criteria import RentalFilter
from marcio_research.domain.value_objects import ListingPrice, LocationSlug, PropertyCode, RoomCount


def build_criteria(arguments: dict[str, Any]) -> RentalFilter:
    locations = tuple(LocationSlug(item) for item in arguments.get("locations", []))
    return RentalFilter(
        locations=locations,
        status="alugar",
        property_types=tuple(arguments.get("property_types", [])),
        bedrooms=_room_count(arguments, "bedrooms"),
        bathrooms=_room_count(arguments, "bathrooms"),
        min_price=_price(arguments, "min_price"),
        max_price=_price(arguments, "max_price"),
        sort=arguments.get("sort", "default"),
        page=arguments.get("page", 1),
        property_id=_property_id(arguments),
        keyword=arguments.get("keyword", ""),
    )


def _room_count(arguments: dict[str, Any], name: str) -> RoomCount | None:
    if name not in arguments:
        return None
    return RoomCount(arguments[name])


def _price(arguments: dict[str, Any], name: str) -> ListingPrice | None:
    if name not in arguments:
        return None
    return ListingPrice(float(arguments[name]))


def _property_id(arguments: dict[str, Any]) -> PropertyCode | None:
    if "property_id" not in arguments:
        return None
    return PropertyCode(arguments["property_id"])
