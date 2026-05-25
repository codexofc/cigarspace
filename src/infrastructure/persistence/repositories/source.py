# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementation of ISourceRecordRepository."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.tasting import SourceRecord
from infrastructure.persistence.mappers import source_to_domain, source_to_model
from infrastructure.persistence.models import SourceRecordModel


class PgSourceRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: SourceRecord) -> SourceRecord:
        m = source_to_model(record)
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return source_to_domain(m)

    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[SourceRecord]:
        stmt = (
            select(SourceRecordModel)
            .where(SourceRecordModel.cigar_id == cigar_id)
            .order_by(SourceRecordModel.fetched_at.desc())
        )
        result = await self._session.execute(stmt)
        return [source_to_domain(m) for m in result.scalars().all()]

    async def find_by_url_hash(self, source_url: str, raw_html_hash: str) -> SourceRecord | None:
        stmt = select(SourceRecordModel).where(
            SourceRecordModel.source_url == source_url,
            SourceRecordModel.raw_html_hash == raw_html_hash,
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return source_to_domain(m) if m else None
