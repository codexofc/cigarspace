# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Unit of Work port — atomic boundary across repositories."""

from __future__ import annotations

from typing import Protocol

from application.ports.api_user_repository import IApiUserRepository
from application.ports.brand_repository import IBrandRepository
from application.ports.cigar_package_repository import ICigarPackageRepository
from application.ports.cigar_repository import ICigarLineRepository, ICigarRepository
from application.ports.customs_repository import (
    ICigarCustomsMatchRepository,
    ICustomsPriceRepository,
    ICustomsPublicationRepository,
    ICustomsSourceRepository,
)
from application.ports.matching_repository import IMatchingRepository
from application.ports.media_blob_repository import IMediaBlobRepository
from application.ports.media_repository import IMediaAssetRepository
from application.ports.refresh_token_repository import IRefreshTokenRepository
from application.ports.source_repository import ISourceRecordRepository


class IUnitOfWork(Protocol):
    """A transactional scope exposing one repository per aggregate."""

    brands: IBrandRepository
    cigar_lines: ICigarLineRepository
    cigars: ICigarRepository
    cigar_packages: ICigarPackageRepository
    customs_sources: ICustomsSourceRepository
    customs_publications: ICustomsPublicationRepository
    customs_prices: ICustomsPriceRepository
    customs_matches: ICigarCustomsMatchRepository
    matching: IMatchingRepository
    source_records: ISourceRecordRepository
    media_assets: IMediaAssetRepository
    media_blobs: IMediaBlobRepository
    api_users: IApiUserRepository
    refresh_tokens: IRefreshTokenRepository

    async def __aenter__(self) -> IUnitOfWork: ...
    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
