# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.brand import Brand
from infrastructure.persistence.repositories.brand import PgBrandRepository

pytestmark = pytest.mark.integration


async def test_add_and_get_by_slug(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgBrandRepository(s)
        created = await repo.add(
            Brand(slug="cohiba", name="Cohiba", country_origin="CUB", founded_year=1966)
        )
        await s.commit()

    async with session_factory() as s:
        repo = PgBrandRepository(s)
        found = await repo.get_by_slug("cohiba")

    assert found is not None
    assert found.id == created.id
    assert found.name == "Cohiba"
    assert found.country_origin == "CUB"
    assert found.founded_year == 1966
    assert found.created_at is not None


async def test_get_by_name(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgBrandRepository(s)
        await repo.add(Brand(slug="padron", name="Padrón", country_origin="NIC"))
        await s.commit()

    async with session_factory() as s:
        repo = PgBrandRepository(s)
        found = await repo.get_by_name("Padrón")

    assert found is not None
    assert found.slug == "padron"


async def test_update_changes_fields(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgBrandRepository(s)
        created = await repo.add(Brand(slug="davidoff", name="Davidoff"))
        await s.commit()

    updated_entity = created.model_copy(
        update={"parent_company": "Oettinger Davidoff AG", "founded_year": 1980}
    )

    async with session_factory() as s:
        repo = PgBrandRepository(s)
        result = await repo.update(updated_entity)
        await s.commit()

    assert result.parent_company == "Oettinger Davidoff AG"
    assert result.founded_year == 1980


async def test_list_all_orders_by_name(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgBrandRepository(s)
        await repo.add(Brand(slug="cohiba", name="Cohiba"))
        await repo.add(Brand(slug="aganorsa", name="Aganorsa"))
        await repo.add(Brand(slug="padron", name="Padrón"))
        await s.commit()

    async with session_factory() as s:
        repo = PgBrandRepository(s)
        names = [b.name for b in await repo.list_all()]
        total = await repo.count()

    assert names == ["Aganorsa", "Cohiba", "Padrón"]
    assert total == 3


async def test_get_unknown_slug_returns_none(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with session_factory() as s:
        repo = PgBrandRepository(s)
        result = await repo.get_by_slug("does-not-exist")

    assert result is None
