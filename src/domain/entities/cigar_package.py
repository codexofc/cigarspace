# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CigarPackage entity — a merchant packaging (box of N) of a canonical cigar.

The Cigar entity remains the canonical reference (one row per vitole).
CigarPackage hangs off it to track per-merchant commercial realities:
pack size (1 / 5 / 25 …), SKU, source URL, listed price. It is informational
— the canonical legal price still comes from Douane FR / opendata.

Idempotency: unique on (cigar_id, source_url). Re-ingesting the same fiche
refreshes price/sku and bumps last_seen_at.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CigarPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    cigar_id: UUID

    pack_size: int = Field(ge=1, le=10_000)
    source_domain: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1, max_length=2048)

    sku: str | None = Field(default=None, max_length=128)
    price_amount: Decimal | None = Field(default=None, ge=0)
    price_currency: str | None = Field(default=None, max_length=3)  # ISO 4217

    is_active: bool = True
    last_seen_at: datetime

    created_at: datetime | None = None
    updated_at: datetime | None = None
