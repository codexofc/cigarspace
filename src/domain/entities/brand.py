# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Brand entity — the cigar manufacturer / marca."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from domain.value_objects.slug import Slug


class Brand(BaseModel):
    """A cigar brand (e.g. Cohiba, Padrón, Davidoff)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    slug: Slug
    name: str = Field(min_length=1, max_length=255)
    country_origin: str | None = Field(default=None, max_length=3)  # ISO 3166-1 alpha-3
    parent_company: str | None = Field(default=None, max_length=255)
    founded_year: int | None = Field(default=None, ge=1492, le=2100)
    is_active: bool = True
    aliases: list[str] = Field(default_factory=list)

    created_at: datetime | None = None
    updated_at: datetime | None = None
