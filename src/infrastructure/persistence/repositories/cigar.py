# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementations of ICigarLineRepository and ICigarRepository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from application.ports.cigar_repository import CigarFilters, CigarSort
from domain.entities.cigar import Cigar
from domain.entities.cigar_line import CigarLine
from infrastructure.persistence.mappers import (
    apply_cigar_line_to_model,
    apply_cigar_to_model,
    blend_to_model,
    cigar_line_to_domain,
    cigar_line_to_model,
    cigar_to_domain,
    cigar_to_model,
)
from infrastructure.persistence.models import BrandModel, CigarLineModel, CigarModel


class PgCigarLineRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, line_id: UUID) -> CigarLine | None:
        m = await self._session.get(CigarLineModel, line_id)
        return cigar_line_to_domain(m) if m else None

    async def get_by_slug(self, brand_id: UUID, slug: str) -> CigarLine | None:
        stmt = select(CigarLineModel).where(
            CigarLineModel.brand_id == brand_id,
            CigarLineModel.slug == slug,
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return cigar_line_to_domain(m) if m else None

    async def get_by_slug_global(self, slug: str) -> CigarLine | None:
        """Lookup by slug ignoring brand_id (slugs are not globally unique
        but disambiguation between brands sharing a line slug is rare;
        callers should still scope by brand when possible)."""
        stmt = select(CigarLineModel).where(CigarLineModel.slug == slug).limit(1)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return cigar_line_to_domain(m) if m else None

    async def add(self, line: CigarLine) -> CigarLine:
        """Idempotent insert on (brand_id, slug)."""

        stmt = (
            pg_insert(CigarLineModel)
            .values(
                id=line.id,
                brand_id=line.brand_id,
                slug=line.slug,
                name=line.name,
                release_year=line.release_year,
                is_limited_edition=line.is_limited_edition,
                description=line.description,
                aliases=list(line.aliases),
            )
            .on_conflict_do_nothing(index_elements=["brand_id", "slug"])
            .returning(CigarLineModel)
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        if m is None:
            existing = await self.get_by_slug(line.brand_id, line.slug)
            assert existing is not None
            return existing
        await self._session.flush()
        return cigar_line_to_domain(m)

    async def update(self, line: CigarLine) -> CigarLine:
        existing = await self._session.get(CigarLineModel, line.id)
        if existing is None:
            raise LookupError(f"CigarLine {line.id} not found")
        apply_cigar_line_to_model(existing, line)
        await self._session.flush()
        await self._session.refresh(existing)
        return cigar_line_to_domain(existing)

    async def list_by_brand(self, brand_id: UUID) -> Sequence[CigarLine]:
        stmt = (
            select(CigarLineModel)
            .where(CigarLineModel.brand_id == brand_id)
            .order_by(CigarLineModel.name)
        )
        result = await self._session.execute(stmt)
        return [cigar_line_to_domain(m) for m in result.scalars().all()]


class PgCigarRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, cigar_id: UUID) -> Cigar | None:
        stmt = (
            select(CigarModel)
            .where(CigarModel.id == cigar_id)
            .options(selectinload(CigarModel.blend_components))
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return cigar_to_domain(m) if m else None

    async def get_by_slug(self, slug: str) -> Cigar | None:
        stmt = (
            select(CigarModel)
            .where(CigarModel.slug == slug)
            .options(selectinload(CigarModel.blend_components))
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return cigar_to_domain(m) if m else None

    async def add(self, cigar: Cigar) -> Cigar:
        """Idempotent insert on `slug`. Blend components are inserted only
        when this call actually creates the cigar (race winner)."""

        stmt = (
            pg_insert(CigarModel)
            .values(
                id=cigar.id,
                line_id=cigar.line_id,
                slug=cigar.slug,
                full_name=cigar.full_name,
                vitola_name=cigar.vitola_name,
                vitola_factory_name=cigar.vitola_factory_name,
                format_category=cigar.format_category,
                length_mm=cigar.length_mm,
                ring_gauge=cigar.ring_gauge,
                ring_gauge_mm=cigar.ring_gauge_mm,
                weight_g=cigar.weight_g,
                draw_resistance_cmh2o=cigar.draw_resistance_cmh2o,
                wrapper_country=cigar.wrapper_country,
                binder_country=cigar.binder_country,
                filler_countries=list(cigar.filler_countries),
                strength=cigar.strength,
                body=cigar.body,
                flavor_profile=cigar.flavor_profile.model_dump(exclude_none=True),
                aging_potential_years=cigar.aging_potential_years,
                is_cuban=cigar.is_cuban,
                is_handmade=cigar.is_handmade,
                is_box_pressed=cigar.is_box_pressed,
                release_year=cigar.release_year,
                discontinued_year=cigar.discontinued_year,
                last_scraped_at=cigar.last_scraped_at,
            )
            .on_conflict_do_nothing(index_elements=["slug"])
            .returning(CigarModel.id)
        )
        result = await self._session.execute(stmt)
        new_id = result.scalar_one_or_none()
        if new_id is None:
            existing = await self.get_by_slug(cigar.slug)
            assert existing is not None
            return existing

        # Winner: persist blend components attached to this cigar
        for bc in cigar.blend_components:
            self._session.add(blend_to_model(bc, cigar_id=new_id))
        await self._session.flush()
        created = await self.get_by_slug(cigar.slug)
        assert created is not None
        return created

    async def update(self, cigar: Cigar) -> Cigar:
        existing = await self._session.get(
            CigarModel,
            cigar.id,
            options=[selectinload(CigarModel.blend_components)],
        )
        if existing is None:
            raise LookupError(f"Cigar {cigar.id} not found")
        apply_cigar_to_model(existing, cigar)
        existing.blend_components = [
            blend_to_model(b, cigar_id=cigar.id) for b in cigar.blend_components
        ]
        await self._session.flush()
        await self._session.refresh(existing, attribute_names=["blend_components"])
        return cigar_to_domain(existing)

    async def list_by_line(self, line_id: UUID) -> Sequence[Cigar]:
        stmt = (
            select(CigarModel)
            .where(CigarModel.line_id == line_id)
            .options(selectinload(CigarModel.blend_components))
            .order_by(CigarModel.full_name)
        )
        result = await self._session.execute(stmt)
        return [cigar_to_domain(m) for m in result.scalars().all()]

    async def list_filtered(
        self,
        *,
        filters: CigarFilters,
        sort: CigarSort,
        limit: int,
        offset: int,
    ) -> Sequence[Cigar]:
        stmt = self._build_filtered_query(filters).options(
            selectinload(CigarModel.blend_components)
        )
        sort_col = _SORT_COLUMNS.get(sort.field, CigarModel.created_at)
        stmt = stmt.order_by(sort_col.desc() if sort.descending else sort_col.asc())
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [cigar_to_domain(m) for m in result.scalars().unique().all()]

    async def count_filtered(self, filters: CigarFilters) -> int:
        stmt = self._build_filtered_query(filters, count=True)
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(CigarModel))
        return int(result.scalar_one())

    def _build_filtered_query(self, filters: CigarFilters, *, count: bool = False):
        needs_brand_join = (
            filters.brand_id is not None
            or filters.brand_slug is not None
            or filters.country_origin is not None
        )
        if count:
            stmt = select(func.count(CigarModel.id.distinct())).select_from(CigarModel)
        else:
            stmt = select(CigarModel)
        if needs_brand_join:
            stmt = stmt.join(CigarLineModel, CigarLineModel.id == CigarModel.line_id)
            stmt = stmt.join(BrandModel, BrandModel.id == CigarLineModel.brand_id)
            if filters.brand_id is not None:
                stmt = stmt.where(BrandModel.id == filters.brand_id)
            if filters.brand_slug is not None:
                stmt = stmt.where(BrandModel.slug == filters.brand_slug)
            if filters.country_origin is not None:
                stmt = stmt.where(BrandModel.country_origin == filters.country_origin)
        if filters.line_id is not None:
            stmt = stmt.where(CigarModel.line_id == filters.line_id)
        if filters.format_category is not None:
            stmt = stmt.where(CigarModel.format_category == filters.format_category)
        if filters.is_cuban is not None:
            stmt = stmt.where(CigarModel.is_cuban == filters.is_cuban)
        if filters.is_handmade is not None:
            stmt = stmt.where(CigarModel.is_handmade == filters.is_handmade)
        if filters.strength is not None:
            stmt = stmt.where(CigarModel.strength == filters.strength)
        if filters.min_length_mm is not None:
            stmt = stmt.where(CigarModel.length_mm >= filters.min_length_mm)
        if filters.max_length_mm is not None:
            stmt = stmt.where(CigarModel.length_mm <= filters.max_length_mm)
        if filters.min_ring_gauge is not None:
            stmt = stmt.where(CigarModel.ring_gauge >= filters.min_ring_gauge)
        if filters.max_ring_gauge is not None:
            stmt = stmt.where(CigarModel.ring_gauge <= filters.max_ring_gauge)
        return stmt


_SORT_COLUMNS = {
    "created_at": CigarModel.created_at,
    "full_name": CigarModel.full_name,
    "length_mm": CigarModel.length_mm,
    "ring_gauge": CigarModel.ring_gauge,
}
