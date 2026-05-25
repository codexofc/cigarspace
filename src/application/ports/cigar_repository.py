# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigar / CigarLine repository contracts."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from domain.entities.cigar import Cigar
from domain.entities.cigar_line import CigarLine
from domain.enums import FormatCategory, Intensity


@dataclass(frozen=True)
class CigarFilters:
    """Filters applied by the API's ``GET /cigars`` listing endpoint.

    None means "do not filter on this dimension". String fields are
    matched exactly (case-insensitive for slug-like fields via ILIKE);
    numeric fields are inclusive bounds.
    """

    brand_id: UUID | None = None
    brand_slug: str | None = None
    line_id: UUID | None = None
    format_category: FormatCategory | None = None
    is_cuban: bool | None = None
    is_handmade: bool | None = None
    country_origin: str | None = None  # brand.country_origin
    strength: Intensity | None = None
    min_length_mm: Decimal | None = None
    max_length_mm: Decimal | None = None
    min_ring_gauge: int | None = None
    max_ring_gauge: int | None = None


@dataclass(frozen=True)
class CigarSort:
    """Sort spec — one of a closed list of allowed fields."""

    field: str = "created_at"  # one of: created_at, full_name, length_mm
    descending: bool = True


class ICigarLineRepository(Protocol):
    async def get_by_id(self, line_id: UUID) -> CigarLine | None: ...
    async def get_by_slug(self, brand_id: UUID, slug: str) -> CigarLine | None: ...
    async def get_by_slug_global(self, slug: str) -> CigarLine | None: ...
    async def add(self, line: CigarLine) -> CigarLine: ...
    async def update(self, line: CigarLine) -> CigarLine: ...
    async def list_by_brand(self, brand_id: UUID) -> Sequence[CigarLine]: ...


class ICigarRepository(Protocol):
    async def get_by_id(self, cigar_id: UUID) -> Cigar | None: ...
    async def get_by_slug(self, slug: str) -> Cigar | None: ...
    async def add(self, cigar: Cigar) -> Cigar: ...
    async def update(self, cigar: Cigar) -> Cigar: ...
    async def list_by_line(self, line_id: UUID) -> Sequence[Cigar]: ...
    async def list_filtered(
        self,
        *,
        filters: CigarFilters,
        sort: CigarSort,
        limit: int,
        offset: int,
    ) -> Sequence[Cigar]: ...
    async def count_filtered(self, filters: CigarFilters) -> int: ...
    async def count(self) -> int: ...
