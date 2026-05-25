# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import infrastructure.customs  # noqa: F401  populate registry
from application.ports.fetcher import FetchRequest, FetchResponse
from application.use_cases.ingest_customs_publication import (
    IngestCustomsPublicationUseCase,
)
from domain.entities.customs import CustomsPublication, CustomsSource
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parents[1] / "fixtures" / "customs" / "legifrance_arrete_synthetic.html"
DOCUMENT_URL = "https://www.legifrance.gouv.fr/jorf/id/ECOI1932471A"


class _BodyFetcher:
    def __init__(self, body: bytes) -> None:
        self._body = body

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=self._body,
            elapsed_s=0.01,
            fetched_at=datetime.now(tz=UTC),
        )

    async def aclose(self) -> None:
        return None


async def _seed_source_and_publication(
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    """Inserts FR source + 1 DISCOVERED publication. Returns the publication UUID."""
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        source = await uow.customs_sources.upsert(
            CustomsSource(
                code="fr-legifrance-jorf",
                country_code="FR",
                display_name="France — Légifrance JORF",
                index_url="https://example/...",
                discovery_parser_name="legifrance-jorf",
                extraction_parser_name="legifrance-html",
                default_currency_code="EUR",
                is_active=True,
            )
        )
        publication = await uow.customs_publications.add(
            CustomsPublication(
                source_id=source.id,
                regulator_reference="ECOI1932471A",
                document_url=DOCUMENT_URL,
                document_mime="text/html",
            )
        )
        await uow.commit()
        return str(publication.id)


async def test_ingests_all_entries(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    pub_id = await _seed_source_and_publication(session_factory)
    body = FIXTURE.read_bytes()
    use_case = IngestCustomsPublicationUseCase(fetcher=_BodyFetcher(body))

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        report = await use_case.execute(publication_id=__import__("uuid").UUID(pub_id), uow=uow)

    assert report.status == "ingested"
    assert report.entries_inserted == 4

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        entries = await uow.customs_prices.find_by_publication(__import__("uuid").UUID(pub_id))
    assert len(entries) == 4
    products = {e.raw_product_label for e in entries}
    assert "Behike BHK 52" in products
    assert all(e.country_code == "FR" for e in entries)
    assert all(e.currency_code == "EUR" for e in entries)


async def test_second_ingest_same_content_is_skipped(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    pub_id = await _seed_source_and_publication(session_factory)
    body = FIXTURE.read_bytes()
    use_case = IngestCustomsPublicationUseCase(fetcher=_BodyFetcher(body))

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        first = await use_case.execute(publication_id=__import__("uuid").UUID(pub_id), uow=uow)
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        second = await use_case.execute(publication_id=__import__("uuid").UUID(pub_id), uow=uow)

    assert first.status == "ingested"
    assert second.status == "skipped_same_hash"

    # Entries didn't multiply on the second pass
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        entries = await uow.customs_prices.find_by_publication(__import__("uuid").UUID(pub_id))
    assert len(entries) == 4


async def test_unknown_publication_returns_not_found(
    session_factory: async_sessionmaker[AsyncSession], clean_db: None
) -> None:
    use_case = IngestCustomsPublicationUseCase(fetcher=_BodyFetcher(b""))
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        report = await use_case.execute(
            publication_id=__import__("uuid").UUID("11111111-1111-1111-1111-111111111111"),
            uow=uow,
        )
    assert report.status == "not_found"
