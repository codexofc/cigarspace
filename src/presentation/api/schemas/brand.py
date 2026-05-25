# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Brand response schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from presentation.api.schemas.base import Links


class BrandResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    slug: str = Field(examples=["cohiba"])
    name: str = Field(examples=["Cohiba"])
    country_origin: str | None = Field(
        default=None,
        description="ISO 3166-1 alpha-3 country code.",
        examples=["CUB"],
    )
    parent_company: str | None = None
    founded_year: int | None = None
    is_active: bool
    aliases: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")
