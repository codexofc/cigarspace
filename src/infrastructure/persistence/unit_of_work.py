# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""SQLAlchemy-backed Unit of Work."""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infrastructure.persistence.repositories.api_user import (
    PgApiUserRepository,
    PgRefreshTokenRepository,
)
from infrastructure.persistence.repositories.brand import PgBrandRepository
from infrastructure.persistence.repositories.cigar import (
    PgCigarLineRepository,
    PgCigarRepository,
)
from infrastructure.persistence.repositories.cigar_package import PgCigarPackageRepository
from infrastructure.persistence.repositories.customs import (
    PgCigarCustomsMatchRepository,
    PgCustomsPriceRepository,
    PgCustomsPublicationRepository,
    PgCustomsSourceRepository,
)
from infrastructure.persistence.repositories.matching import PgMatchingRepository
from infrastructure.persistence.repositories.media import PgMediaAssetRepository
from infrastructure.persistence.repositories.media_blob import PgMediaBlobRepository
from infrastructure.persistence.repositories.source import PgSourceRecordRepository


class SqlAlchemyUnitOfWork:
    """One session = one transactional scope = one UoW.

    Implements application.ports.IUnitOfWork structurally (Protocol).
    """

    brands: PgBrandRepository
    cigar_lines: PgCigarLineRepository
    cigars: PgCigarRepository
    cigar_packages: PgCigarPackageRepository
    customs_sources: PgCustomsSourceRepository
    customs_publications: PgCustomsPublicationRepository
    customs_prices: PgCustomsPriceRepository
    customs_matches: PgCigarCustomsMatchRepository
    matching: PgMatchingRepository
    source_records: PgSourceRecordRepository
    media_assets: PgMediaAssetRepository
    media_blobs: PgMediaBlobRepository
    api_users: PgApiUserRepository
    refresh_tokens: PgRefreshTokenRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._committed = False

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._session_factory()
        self._committed = False
        self.brands = PgBrandRepository(self._session)
        self.cigar_lines = PgCigarLineRepository(self._session)
        self.cigars = PgCigarRepository(self._session)
        self.cigar_packages = PgCigarPackageRepository(self._session)
        self.customs_sources = PgCustomsSourceRepository(self._session)
        self.customs_publications = PgCustomsPublicationRepository(self._session)
        self.customs_prices = PgCustomsPriceRepository(self._session)
        self.customs_matches = PgCigarCustomsMatchRepository(self._session)
        self.matching = PgMatchingRepository(self._session)
        self.source_records = PgSourceRecordRepository(self._session)
        self.media_assets = PgMediaAssetRepository(self._session)
        self.media_blobs = PgMediaBlobRepository(self._session)
        self.api_users = PgApiUserRepository(self._session)
        self.refresh_tokens = PgRefreshTokenRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def commit(self) -> None:
        assert self._session is not None, "UnitOfWork must be entered via 'async with'"
        await self._session.commit()
        self._committed = True

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()
