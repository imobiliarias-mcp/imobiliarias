"""Safe raw-data projections for Viva Real listings and details."""

import json
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from vivareal_research.parsers.page_payload_parser import VivaRealPagePayloadParser

from rental_bridge.transport.safe_http import safe_url

PROVIDER = "vivareal"
PUBLIC_BASE = "https://www.vivareal.com.br"


def _first_value(value: Any) -> Any:
    if not isinstance(value, list):
        return value
    if not value:
        return None
    return value[0]


def _integer(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _rental_pricing(listing: dict[str, Any]) -> dict[str, Any]:
    entries = listing.get("pricingInfos", [])
    if isinstance(entries, list) and entries:
        selected = next((entry for entry in entries if entry.get("businessType") == "RENTAL"), entries[0])
        nested = selected.get("rentalInfo", {})
        return {"rent": selected.get("price"), "condo": selected.get("monthlyCondoFee"),
                "iptu": selected.get("yearlyIptu"), "total": nested.get("monthlyRentalTotalPrice")}
    prices = listing.get("prices", {})
    rental = {}
    if isinstance(prices, dict):
        rental = prices.get("rental", {})
    return {"rent": rental.get("value"), "condo": rental.get("condominium"),
            "iptu": rental.get("iptu"), "total": rental.get("monthlyRentalTotalPrice")}


def _feature_values(listing: dict[str, Any]) -> dict[str, int | None]:
    raw = listing
    amenities = listing.get("amenities")
    if isinstance(amenities, dict):
        raw = amenities
    return {"usable_area": _integer(_first_value(raw.get("usableAreas"))),
            "bedrooms": _integer(_first_value(raw.get("bedrooms"))),
            "bathrooms": _integer(_first_value(raw.get("bathrooms"))),
            "suites": _integer(_first_value(raw.get("suites"))),
            "parking_spaces": _integer(_first_value(raw.get("parkingSpaces")))}


def _address(item: Any) -> dict[str, Any]:
    address = item.address
    return {"neighborhood": address.neighborhood, "city": address.city,
            "state_acronym": address.state_acronym, "street": address.street,
            "street_number": address.street_number, "zip_code": address.zip_code,
            "latitude": address.latitude, "longitude": address.longitude}


def _native_pricing(pricing: dict[str, Any]) -> dict[str, int | None]:
    return {"monthly_rent": _integer(pricing["rent"]),
            "monthly_condo": _integer(pricing["condo"]),
            "yearly_iptu": _integer(pricing["iptu"]),
            "total_monthly": _integer(pricing["total"])}


def _canonical_url(item: Any) -> str:
    return safe_url(item.canonical_url, PROVIDER)


def suggestion_coordinate(item: Any) -> dict[str, float] | None:
    if item.coordinate is None:
        return None
    return {"latitude": item.coordinate.latitude, "longitude": item.coordinate.longitude}


def listing_native(item: Any, raw_item: dict[str, Any], fallback_rent: Any = None) -> dict[str, Any]:
    """Project parsed and raw listing values without inventing missing amounts."""
    raw_listing = raw_item.get("listing", raw_item)
    pricing = _rental_pricing(raw_listing)
    if pricing["rent"] is None:
        pricing["rent"] = fallback_rent
    return {"listing_id": item.listing_id, "external_id": item.external_id,
            "title": item.title, "address": _address(item), "pricing": _native_pricing(pricing),
            "features": _feature_values(raw_listing), "photos_count": item.photos_count,
            "canonical_url": _canonical_url(item), "advertiser_name": item.advertiser_name}


def listing_display(item: Any, native: dict[str, Any]) -> dict[str, Any]:
    """Build a compact display card using the validated listing URL."""
    address = item.address
    location = ", ".join(part for part in (address.neighborhood, address.city, address.state_acronym) if part)
    url = native["canonical_url"]
    return {"reference": url, "url": url, "title": item.title,
            "location": location or None, "price": native["pricing"]["monthly_rent"]}


def detail_listing(raw_html: str) -> dict[str, Any]:
    """Parse raw property HTML for explicit pricing and feature values."""
    return VivaRealPagePayloadParser().parse(BeautifulSoup(raw_html, "html.parser"))


def product_price(raw_html: str) -> Any:
    """Extract an explicit Product offer price from JSON-LD, when available."""
    soup = BeautifulSoup(raw_html, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    return next((_product_offer(script.string or "{}") for script in scripts
                 if _is_product(script.string or "{}")), None)


def _is_product(document: str) -> bool:
    try:
        return json.loads(document).get("@type") == "Product"
    except (json.JSONDecodeError, AttributeError):
        return False


def _product_offer(document: str) -> Any:
    try:
        product = json.loads(document)
    except json.JSONDecodeError:
        return None
    offers = product.get("offers", {})
    if not isinstance(offers, dict):
        return None
    return offers.get("price")


def detail_native(detail: Any, raw_listing: dict[str, Any], fallback_rent: Any) -> dict[str, Any]:
    """Project public detail fields while preserving unknown raw values."""
    summary = listing_native(detail.summary, raw_listing, fallback_rent)
    content = detail.content
    return {"summary": summary, "content": {
        "description": content.description, "amenities": list(content.amenities),
        "gallery": list(content.gallery.image_urls),
        "contact": {"name": content.contact.name, "phone": content.contact.phone,
                    "whatsapp": content.contact.whatsapp, "profile_url": content.contact.profile_url}}}


def detail_display(detail: Any, native: dict[str, Any], public_url: str) -> dict[str, Any]:
    """Build the detail display card around its canonical public reference."""
    address = detail.summary.address
    location = ", ".join(part for part in (address.neighborhood, address.city, address.state_acronym) if part)
    return {"reference": public_url, "url": public_url, "title": detail.summary.title,
            "location": location or None, "price": native["summary"]["pricing"]["monthly_rent"]}


def canonical_detail_url(detail: Any, requested_url: str) -> str:
    """Resolve and validate a detail's public canonical URL."""
    path = detail.summary.canonical_url or requested_url
    return safe_url(urljoin(PUBLIC_BASE + "/", path), PROVIDER)
