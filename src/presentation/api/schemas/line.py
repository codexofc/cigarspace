# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CigarLine response schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from presentation.api.schemas.base import Links


class LineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    brand_id: UUID
    slug: str = Field(examples=["behike"])
    name: str = Field(examples=["Behike"])
    release_year: int | None = None
    is_limited_edition: bool
    description: str | None = None
    aliases: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")
