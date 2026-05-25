# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Parser ports — abstract contracts for extracting structured data from HTML.

Two complementary parsers per source site:
- IListingParser   : a category / search page → URLs of product detail pages
                     and the URL of the next listing page (if any).
- IProductParser   : one product detail page → a ProductExtraction DTO
                     that the application layer maps into domain entities.

The DTOs intentionally stay *flat and merchant-flavored*: they reflect
what the source actually provides, not the canonical domain model. The
mapping to Cigar / Brand / BlendComponent happens in the use case.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Listing parser
# ---------------------------------------------------------------------------


class ListingExtraction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_urls: list[str] = Field(default_factory=list)
    next_page_url: str | None = None


class IListingParser(Protocol):
    def parse_listing(self, *, html: str, page_url: str) -> ListingExtraction: ...


# ---------------------------------------------------------------------------
# Product parser
# ---------------------------------------------------------------------------


class BlendLeafExtraction(BaseModel):
    """One tobacco leaf as the merchant describes it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str = Field(min_length=1, max_length=64)  # "wrapper" | "binder" | "filler"
    origin_text: str = Field(min_length=1, max_length=255)


class ProductExtraction(BaseModel):
    """Source-flavored extraction of a product detail page.

    All optional fields are None when the merchant didn't expose them.
    Numeric fields are already typed (Decimal/int) when present.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Provenance
    source_url: str
    source_domain: str

    # Identification
    title: str  # e.g. "Vallejuelo Churchill (1)"
    sku: str | None = None
    brand_name: str | None = None
    manufacturer: str | None = None  # e.g. "Tabacalera Privada"

    # Format
    vitola_name: str | None = None  # e.g. "Churchill"
    length_mm: Decimal | None = None
    ring_gauge: int | None = None  # CEPO
    ring_gauge_mm: Decimal | None = None
    weight_g: Decimal | None = None

    # Composition (leaves) — raw merchant strings, mapped to domain enums later
    wrapper_origin: str | None = None
    binder_origin: str | None = None
    filler_origins: list[str] = Field(default_factory=list)

    # Production origin
    production_country: str | None = None  # "République dominicaine"
    terroir: str | None = None

    # Sensorial
    strength_text: str | None = None  # raw, e.g. "● ● ● ● ○"
    strength_level: int | None = None  # filled bullets 0..5

    # Smoke duration (free text → may parse to range)
    duration_text: str | None = None  # e.g. "80 – 100 minutes"

    # Packaging — informational. The canonical cigar is the same reference
    # whether sold solo or boxed, so pack_size feeds the SourceRecord audit
    # trail but does NOT create distinct Cigar rows.
    pack_size: int | None = None  # 1 (à l'unité), 5, 10, 25, …

    # Pricing (informational; canonical price comes from Douane). Always
    # expressed for ONE PACK of pack_size cigars at the merchant.
    price_amount: Decimal | None = None
    price_currency: str | None = None  # ISO 4217 (e.g. "CHF")

    # Media
    primary_image_url: str | None = None

    # Composition (structured)
    blend_leaves: list[BlendLeafExtraction] = Field(default_factory=list)

    # Catch-all for source-specific attributes we don't promote to fields yet
    raw_attributes: dict[str, Any] = Field(default_factory=dict)


class IProductParser(Protocol):
    def parse_product(self, *, html: str, page_url: str) -> ProductExtraction: ...
