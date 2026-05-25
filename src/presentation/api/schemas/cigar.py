# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigar response schemas (summary + detail)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import (
    BlendComponentType,
    Confidence,
    FormatCategory,
    Intensity,
)
from presentation.api.schemas.base import Links


class BlendComponentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_type: BlendComponentType
    tobacco_origin: str | None = None
    tobacco_region: str | None = None
    tobacco_variety: str | None = None
    aging_years: int | None = None
    percentage: Decimal | None = None
    source_confidence: Confidence


class CigarSummary(BaseModel):
    """Lightweight payload used in lists and search hits."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    slug: str
    full_name: str
    vitola_name: str
    format_category: FormatCategory
    is_cuban: bool
    links: Links = Field(alias="_links")


class CigarResponse(BaseModel):
    """Full cigar detail with blend, dimensions, tasting profile."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    line_id: UUID
    slug: str
    full_name: str
    vitola_name: str
    vitola_factory_name: str | None = None
    format_category: FormatCategory

    length_mm: Decimal | None = None
    ring_gauge: int | None = None
    ring_gauge_mm: Decimal | None = None
    weight_g: Decimal | None = None
    draw_resistance_cmh2o: Decimal | None = None

    wrapper_country: str | None = None
    binder_country: str | None = None
    filler_countries: list[str] = Field(default_factory=list)

    strength: Intensity | None = None
    body: Intensity | None = None
    flavor_profile: dict[str, Any] = Field(default_factory=dict)

    aging_potential_years: int | None = None
    is_cuban: bool
    is_handmade: bool
    is_box_pressed: bool
    release_year: int | None = None
    discontinued_year: int | None = None

    blend_components: list[BlendComponentResponse] = Field(default_factory=list)

    last_scraped_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")
