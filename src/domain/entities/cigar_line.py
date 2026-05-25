# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CigarLine entity — a product range within a brand."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from domain.value_objects.slug import Slug


class CigarLine(BaseModel):
    """A line / range within a brand (e.g. Cohiba Behike, Padrón 1964)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    brand_id: UUID
    slug: Slug
    name: str = Field(min_length=1, max_length=255)
    release_year: int | None = Field(default=None, ge=1700, le=2100)
    is_limited_edition: bool = False
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)

    created_at: datetime | None = None
    updated_at: datetime | None = None
