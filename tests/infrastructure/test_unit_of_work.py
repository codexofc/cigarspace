# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.brand import Brand
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration


async def test_commit_persists(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.brands.add(Brand(slug="ashton", name="Ashton"))
        await uow.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        found = await uow.brands.get_by_slug("ashton")
        assert found is not None


async def test_implicit_rollback_on_exit_without_commit(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.brands.add(Brand(slug="ashton", name="Ashton"))
        # no commit

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        found = await uow.brands.get_by_slug("ashton")
        assert found is None


async def test_rollback_on_exception(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    with pytest.raises(RuntimeError):
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            await uow.brands.add(Brand(slug="ashton", name="Ashton"))
            raise RuntimeError("boom")

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        found = await uow.brands.get_by_slug("ashton")
        assert found is None
