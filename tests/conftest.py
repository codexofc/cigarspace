"""Root conftest — environment, DB fixtures shared by all sub-suites.

- Sets APP_ENV=test and LOG_LEVEL=WARNING BEFORE any cigars import.
- Provides the `engine`, `session_factory` and `clean_db` fixtures used
  by both tests/infrastructure/ and tests/application/.
- (Re)creates the cigars_test database once per session via an admin
  connection and loads the ORM schema via Base.metadata.create_all
  (faster than Alembic, sidesteps Alembic's own asyncio.run nesting).

Pure-unit tests under tests/domain/ and tests/presentation/ don't depend
on the DB; the autouse session fixture still runs once but only adds
~1 s of overhead per pytest run.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")

TEST_DB_NAME = "cigars_test"
os.environ["POSTGRES_DB"] = TEST_DB_NAME

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Register all ORM classes on Base.metadata before fixtures run.
from infrastructure.config import get_settings  # noqa: E402
from infrastructure.persistence import models as _orm_models  # noqa: E402, F401
from infrastructure.persistence.base import Base  # noqa: E402


def _admin_dsn() -> str:
    pg = get_settings().postgres
    return f"postgresql+asyncpg://{pg.user}:{pg.password}@{pg.host}:{pg.port}/postgres"


def _test_dsn() -> str:
    return get_settings().postgres.dsn


async def _recreate_database() -> None:
    admin_engine = create_async_engine(_admin_dsn(), isolation_level="AUTOCOMMIT")
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    f"WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()"
                )
            )
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}"'))
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    finally:
        await admin_engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _migrate_test_db() -> AsyncIterator[None]:
    await _recreate_database()

    eng = create_async_engine(_test_dsn())
    try:
        async with eng.begin() as conn:
            # Extensions must exist before SQLAlchemy creates tables that
            # reference their types:
            #   - pgvector → cigar.embedding
            #   - citext   → api_user.email
            #   - pg_trgm  → trigram indexes on cigar/brand names
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await eng.dispose()

    yield


@pytest_asyncio.fixture(scope="session")
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(_test_dsn(), pool_pre_ping=True)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture
async def clean_db(engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE "
                "refresh_token, api_user, "
                "cigar_customs_match, customs_price_entry, customs_publication, "
                "customs_source, tasting_note, source_record, media_asset, "
                "media_blob, cigar_package, blend_component, cigar, "
                "cigar_line, brand "
                "RESTART IDENTITY CASCADE"
            )
        )
