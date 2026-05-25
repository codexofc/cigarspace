# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementation of IMediaAssetRepository."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.media import MediaAsset
from domain.enums import MediaStatus
from infrastructure.persistence.mappers import media_to_domain, media_to_model
from infrastructure.persistence.models import MediaAssetModel


class PgMediaAssetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, asset: MediaAsset) -> MediaAsset:
        m = media_to_model(asset)
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return media_to_domain(m)

    async def get_by_id(self, asset_id: UUID) -> MediaAsset | None:
        m = await self._session.get(MediaAssetModel, asset_id)
        return media_to_domain(m) if m else None

    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[MediaAsset]:
        stmt = (
            select(MediaAssetModel)
            .where(MediaAssetModel.cigar_id == cigar_id)
            .order_by(MediaAssetModel.is_primary.desc(), MediaAssetModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [media_to_domain(m) for m in result.scalars().all()]

    async def find_for_cigar_and_url(self, cigar_id: UUID, original_url: str) -> MediaAsset | None:
        stmt = select(MediaAssetModel).where(
            MediaAssetModel.cigar_id == cigar_id,
            MediaAssetModel.original_url == original_url,
        )
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return media_to_domain(m) if m else None

    async def find_pending(self, limit: int = 100) -> Sequence[MediaAsset]:
        stmt = (
            select(MediaAssetModel)
            .where(MediaAssetModel.status == MediaStatus.PENDING)
            .order_by(MediaAssetModel.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [media_to_domain(m) for m in result.scalars().all()]

    async def mark_status(
        self,
        asset_id: UUID,
        *,
        status: MediaStatus,
        media_blob_hash: str | None = None,
    ) -> MediaAsset:
        existing = await self._session.get(MediaAssetModel, asset_id)
        if existing is None:
            raise LookupError(f"MediaAsset {asset_id} not found")
        existing.status = status
        if media_blob_hash is not None:
            existing.media_blob_hash = media_blob_hash
        if status == MediaStatus.OK and existing.downloaded_at is None:
            existing.downloaded_at = datetime.now(tz=timezone.utc)
        await self._session.flush()
        await self._session.refresh(existing)
        return media_to_domain(existing)
