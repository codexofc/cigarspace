# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigar entity — the canonical reference unit + its blend components."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import BlendComponentType, Confidence, FormatCategory, Intensity
from domain.value_objects.flavor_profile import FlavorProfile
from domain.value_objects.slug import Slug


class BlendComponent(BaseModel):
    """One tobacco leaf participating in the cigar's blend."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    cigar_id: UUID | None = None  # set when persisted
    component_type: BlendComponentType
    tobacco_origin: str | None = Field(default=None, max_length=120)
    tobacco_region: str | None = Field(default=None, max_length=120)
    tobacco_variety: str | None = Field(default=None, max_length=120)
    aging_years: int | None = Field(default=None, ge=0, le=100)
    percentage: Decimal | None = Field(default=None, ge=0, le=100)
    source_confidence: Confidence = Confidence.UNVERIFIED

    created_at: datetime | None = None
    updated_at: datetime | None = None


class Cigar(BaseModel):
    """A specific cigar reference (brand + line + vitola)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    line_id: UUID
    slug: Slug
    full_name: str = Field(min_length=1, max_length=255)

    # Vitola
    vitola_name: str = Field(min_length=1, max_length=120)
    vitola_factory_name: str | None = Field(default=None, max_length=120)
    format_category: FormatCategory = FormatCategory.OTHER

    # Dimensions (flattened for queryability)
    length_mm: Decimal | None = Field(default=None, ge=0, le=500)
    ring_gauge: int | None = Field(default=None, ge=20, le=80)
    ring_gauge_mm: Decimal | None = Field(default=None, ge=0, le=50)
    weight_g: Decimal | None = Field(default=None, ge=0, le=500)  # per single cigar
    draw_resistance_cmh2o: Decimal | None = Field(default=None, ge=0, le=500)

    # Blend metadata (full components live in BlendComponent)
    wrapper_country: str | None = Field(default=None, max_length=3)
    binder_country: str | None = Field(default=None, max_length=3)
    filler_countries: list[str] = Field(default_factory=list)

    # Tasting metadata
    strength: Intensity | None = None
    body: Intensity | None = None
    flavor_profile: FlavorProfile = Field(default_factory=FlavorProfile)

    # Production
    aging_potential_years: int | None = Field(default=None, ge=0, le=100)
    is_cuban: bool = False
    is_handmade: bool = True
    is_box_pressed: bool = False
    release_year: int | None = Field(default=None, ge=1700, le=2100)
    discontinued_year: int | None = Field(default=None, ge=1700, le=2100)

    # Operational
    last_scraped_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Aggregated collection (populated on read, optional on write)
    blend_components: list[BlendComponent] = Field(default_factory=list)
