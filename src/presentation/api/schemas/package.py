# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CigarPackage response schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from presentation.api.schemas.base import Links


class PackageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    cigar_id: UUID
    pack_size: int = Field(ge=1)
    source_domain: str
    source_url: str
    sku: str | None = None
    price_amount: Decimal | None = None
    price_currency: str | None = None
    is_active: bool
    last_seen_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")
