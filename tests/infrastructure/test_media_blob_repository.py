# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.media_blob import MediaBlob
from infrastructure.persistence.repositories.media_blob import PgMediaBlobRepository

pytestmark = pytest.mark.integration


def _blob(content_hash: str = "a" * 64) -> MediaBlob:
    return MediaBlob(
        content_hash=content_hash,
        storage_key=f"{content_hash[:2]}/{content_hash}.webp",
        mime_type="image/webp",
        byte_size=12_345,
        width_px=800,
        height_px=600,
        first_seen_at=datetime.now(tz=UTC),
    )


async def test_add_inserts_new_blob(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgMediaBlobRepository(s)
        blob, inserted = await repo.add(_blob())
        await s.commit()
    assert inserted is True
    assert blob.content_hash == "a" * 64


async def test_add_is_idempotent_on_content_hash(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgMediaBlobRepository(s)
        b1, ins1 = await repo.add(_blob())
        b2, ins2 = await repo.add(_blob())  # same hash, different instance
        await s.commit()
    assert ins1 is True and ins2 is False
    assert b1.content_hash == b2.content_hash
    assert b1.storage_key == b2.storage_key


async def test_get_by_hash(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgMediaBlobRepository(s)
        await repo.add(_blob("b" * 64))
        await s.commit()

    async with session_factory() as s:
        repo = PgMediaBlobRepository(s)
        found = await repo.get_by_hash("b" * 64)
        missing = await repo.get_by_hash("c" * 64)

    assert found is not None
    assert found.storage_key.startswith("bb/")
    assert missing is None
