"""Web-facing rental listing combining a search projection with detail media."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from central_mcp.web.normalizer import (
    normalize_cover_fallback,
    normalize_description,
    normalize_http_url,
    normalize_photos,
)


@dataclass(frozen=True)
class WebListing:
    """One rental listing ready for the browser, with cover photo and description."""

    provider: str
    code: str | None
    title: str | None
    location: str | None
    city: str | None
    neighborhood: str | None
    transaction: str | None
    rent_price: float | None
    condo_fee: float | None
    iptu: float | None
    total_price: float | None
    bedrooms: int | None
    official_url: str | None
    photos: tuple[str, ...]
    description: str | None

    @classmethod
    def from_parts(cls, projected: dict[str, Any], detail: dict[str, Any] | None) -> WebListing:
        """Build a listing from a search projection and an optional detail payload."""
        media_source = detail or {}
        return cls(
            provider=str(projected.get("provider", "")),
            code=projected.get("code"),
            title=projected.get("title"),
            location=projected.get("location"),
            city=projected.get("city"),
            neighborhood=projected.get("neighborhood"),
            transaction=projected.get("transaction"),
            rent_price=projected.get("rent_price"),
            condo_fee=projected.get("condo_fee"),
            iptu=projected.get("iptu"),
            total_price=projected.get("total_price"),
            bedrooms=projected.get("bedrooms"),
            official_url=normalize_http_url(projected.get("url")),
            photos=_photos_for(projected, media_source),
            description=normalize_description(media_source),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict, including the cover photo."""
        return {
            "provider": self.provider,
            "code": self.code,
            "title": self.title,
            "location": self.location,
            "city": self.city,
            "neighborhood": self.neighborhood,
            "transaction": self.transaction,
            "rent_price": self.rent_price,
            "condo_fee": self.condo_fee,
            "iptu": self.iptu,
            "total_price": self.total_price,
            "bedrooms": self.bedrooms,
            "official_url": self.official_url,
            "cover_photo": self.photos[0] if self.photos else None,
            "photos": list(self.photos),
            "description": self.description,
        }


def _photos_for(projected: dict[str, Any], detail: dict[str, Any]) -> tuple[str, ...]:
    """Prefer the detail gallery, then the detail's single cover, then the search payload's media."""
    gallery = normalize_photos(detail)
    if gallery:
        return gallery
    detail_cover = normalize_cover_fallback(detail)
    if detail_cover:
        return detail_cover
    raw = projected.get("raw")
    if not isinstance(raw, dict):
        return ()
    return normalize_photos(raw) or normalize_cover_fallback(raw)
