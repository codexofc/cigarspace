# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementation of IMediaBlobRepository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.media_blob import MediaBlob
from infrastructure.persistence.mappers import media_blob_to_domain
from infrastructure.persistence.models import MediaBlobModel


class PgMediaBlobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, blob: MediaBlob) -> tuple[MediaBlob, bool]:
        """Insert idempotently on content_hash. Returns (blob, was_inserted)."""

        stmt = (
            pg_insert(MediaBlobModel)
            .values(
                content_hash=blob.content_hash,
                storage_key=blob.storage_key,
                mime_type=blob.mime_type,
                byte_size=blob.byte_size,
                width_px=blob.width_px,
                height_px=blob.height_px,
                first_seen_at=blob.first_seen_at,
            )
            .on_conflict_do_nothing(index_elements=["content_hash"])
            .returning(MediaBlobModel.content_hash)
        )
        # ON CONFLICT DO NOTHING + RETURNING: yields a row only when an INSERT
        # actually happened. asyncpg's rowcount is unreliable for DML, so we
        # rely on the presence/absence of the returned value to detect inserts.
        result = await self._session.execute(stmt)
        returned_hash = result.scalar_one_or_none()
        inserted = returned_hash is not None
        await self._session.flush()
        saved = await self.get_by_hash(blob.content_hash)
        assert saved is not None, "media_blob disappeared right after insert"
        return saved, inserted

    async def get_by_hash(self, content_hash: str) -> MediaBlob | None:
        stmt = select(MediaBlobModel).where(MediaBlobModel.content_hash == content_hash)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return media_blob_to_domain(m) if m else None
