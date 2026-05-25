# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementation of ICigarPackageRepository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.cigar_package import CigarPackage
from infrastructure.persistence.mappers import (
    apply_cigar_package_to_model,
    cigar_package_to_domain,
    cigar_package_to_model,
)
from infrastructure.persistence.models import CigarPackageModel


class PgCigarPackageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, package: CigarPackage) -> CigarPackage:
        m = cigar_package_to_model(package)
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return cigar_package_to_domain(m)

    async def update(self, package: CigarPackage) -> CigarPackage:
        existing = await self._session.get(CigarPackageModel, package.id)
        if existing is None:
            raise LookupError(f"CigarPackage {package.id} not found")
        apply_cigar_package_to_model(existing, package)
        await self._session.flush()
        await self._session.refresh(existing)
        return cigar_package_to_domain(existing)

    async def find_by_cigar_and_url(self, cigar_id: UUID, source_url: str) -> CigarPackage | None:
        stmt = select(CigarPackageModel).where(
            CigarPackageModel.cigar_id == cigar_id,
            CigarPackageModel.source_url == source_url,
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return cigar_package_to_domain(m) if m else None

    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[CigarPackage]:
        stmt = (
            select(CigarPackageModel)
            .where(CigarPackageModel.cigar_id == cigar_id)
            .order_by(CigarPackageModel.pack_size)
        )
        result = await self._session.execute(stmt)
        return [cigar_package_to_domain(m) for m in result.scalars().all()]
