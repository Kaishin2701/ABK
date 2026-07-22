from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProductData:
    url: str
    title: str | None = None
    sku: str | None = None
    tags: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    short_description: str | None = None
    review_count: int = 0
    base_price: float | None = None
    size_prices: list[dict[str, Any]] = field(default_factory=list)
    global_form: list[dict[str, Any]] = field(default_factory=list)
    image_count: dict[str, int] = field(default_factory=dict)
    image_details: list[dict[str, str | None]] = field(default_factory=list)
    long_description: str | None = None
    description_headings: list[str] = field(default_factory=list)
    additional_information: dict[str, str] = field(default_factory=dict)
    printed: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "sku": self.sku,
            "tags": self.tags,
            "categories": self.categories,
            "short_description": self.short_description,
            "review_count": self.review_count,
            "base_price": self.base_price,
            "size_prices": self.size_prices,
            "global_form": self.global_form,
            "image_count": self.image_count,
            "image_details": self.image_details,
            "long_description": self.long_description,
            "description_headings": self.description_headings,
            "additional_information": self.additional_information,
            "printed": self.printed,
        }
