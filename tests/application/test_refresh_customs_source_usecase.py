# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import infrastructure.customs  # noqa: F401  populate registry
from application.ports.fetcher import FetchRequest, FetchResponse
from application.use_cases.refresh_customs_source import RefreshCustomsSourceUseCase
from domain.entities.customs import CustomsSource
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parents[1] / "fixtures" / "customs" / "legifrance_index_synthetic.html"
INDEX_URL = "https://www.legifrance.gouv.fr/search/jorf?fonds=JORF&q=test"


class _CannedFetcher:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=self._body,
            elapsed_s=0.01,
            fetched_at=datetime.now(tz=timezone.utc),
        )

    async def aclose(self) -> None:
        return None


async def _seed_fr_source(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.customs_sources.upsert(
            CustomsSource(
                code="fr-legifrance-jorf",
                country_code="FR",
                display_name="France — Légifrance JORF",
                index_url=INDEX_URL,
                discovery_parser_name="legifrance-jorf",
                extraction_parser_name="legifrance-html",
                default_currency_code="EUR",
                is_active=True,
            )
        )
        await uow.commit()


async def test_first_refresh_creates_all_publications(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    await _seed_fr_source(session_factory)
    body = FIXTURE.read_bytes()
    use_case = RefreshCustomsSourceUseCase(fetcher=_CannedFetcher(body))

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        report = await use_case.execute(source_code="fr-legifrance-jorf", uow=uow)

    assert report.error is None
    assert report.total_seen == 3
    assert report.new_publications == 3
    assert len(report.new_publication_ids) == 3


async def test_second_refresh_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    await _seed_fr_source(session_factory)
    body = FIXTURE.read_bytes()
    use_case = RefreshCustomsSourceUseCase(fetcher=_CannedFetcher(body))

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        first = await use_case.execute(source_code="fr-legifrance-jorf", uow=uow)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        second = await use_case.execute(source_code="fr-legifrance-jorf", uow=uow)

    assert first.new_publications == 3
    assert second.new_publications == 0
    assert second.total_seen == 3


async def test_inactive_source_returns_error(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.customs_sources.upsert(
            CustomsSource(
                code="ch-ofdf",
                country_code="CH",
                display_name="Suisse",
                index_url="TBD",
                discovery_parser_name="generic-html-index",
                extraction_parser_name="ofdf-generic",
                default_currency_code="CHF",
                is_active=False,
            )
        )
        await uow.commit()

    use_case = RefreshCustomsSourceUseCase(fetcher=_CannedFetcher(b""))
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        report = await use_case.execute(source_code="ch-ofdf", uow=uow)

    assert report.error == "source_inactive"
    assert report.new_publications == 0


async def test_unknown_source_returns_error(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    use_case = RefreshCustomsSourceUseCase(fetcher=_CannedFetcher(b""))
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        report = await use_case.execute(source_code="does-not-exist", uow=uow)
    assert report.error == "source_not_found"
