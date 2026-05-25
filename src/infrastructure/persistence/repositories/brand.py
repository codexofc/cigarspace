# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementation of IBrandRepository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.brand import Brand
from infrastructure.persistence.mappers import (
    apply_brand_to_model,
    brand_to_domain,
)
from infrastructure.persistence.models import BrandModel


class PgBrandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, brand_id):
        m = await self._session.get(BrandModel, brand_id)
        return brand_to_domain(m) if m else None

    async def get_by_slug(self, slug: str) -> Brand | None:
        stmt = select(BrandModel).where(BrandModel.slug == slug)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return brand_to_domain(m) if m else None

    async def get_by_name(self, name: str) -> Brand | None:
        stmt = select(BrandModel).where(BrandModel.name == name)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return brand_to_domain(m) if m else None

    async def add(self, brand: Brand) -> Brand:
        """Idempotent insert on `slug`.

        Two parallel workers can call add() with the same slug; the second
        one will trigger an ON CONFLICT DO NOTHING and we refetch the
        existing row instead of crashing on a unique-constraint violation.
        """

        stmt = (
            pg_insert(BrandModel)
            .values(
                id=brand.id,
                slug=brand.slug,
                name=brand.name,
                country_origin=brand.country_origin,
                parent_company=brand.parent_company,
                founded_year=brand.founded_year,
                is_active=brand.is_active,
                aliases=list(brand.aliases),
            )
            .on_conflict_do_nothing(index_elements=["slug"])
            .returning(BrandModel)
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        if m is None:
            # Lost the race — fetch the existing row
            existing = await self.get_by_slug(brand.slug)
            assert existing is not None, "ON CONFLICT DO NOTHING with no row?"
            return existing
        await self._session.flush()
        return brand_to_domain(m)

    async def update(self, brand: Brand) -> Brand:
        existing = await self._session.get(BrandModel, brand.id)
        if existing is None:
            raise LookupError(f"Brand {brand.id} not found")
        apply_brand_to_model(existing, brand)
        await self._session.flush()
        await self._session.refresh(existing)
        return brand_to_domain(existing)

    async def list_all(self, limit: int = 100, offset: int = 0) -> Sequence[Brand]:
        stmt = select(BrandModel).order_by(BrandModel.name).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return [brand_to_domain(m) for m in result.scalars().all()]

    async def count(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(BrandModel))
        return int(result.scalar_one())
