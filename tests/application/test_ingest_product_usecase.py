# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.fetcher import FetchRequest, FetchResponse
from application.use_cases.ingest_product import (
    IngestOutcome,
    IngestProductUrlUseCase,
)
from infrastructure.parsers.mistercigar import MistercigarProductParser
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[1] / "fixtures"
DETAIL_URL = "https://mistercigar.com/boutique/cigares/cigares-a-lunite/vallejuelo-churchill-1/"


class _CannedFetcher:
    """Replays a FetchResponse from a saved HTML fixture — no network."""

    def __init__(self, *, body: bytes) -> None:
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


@pytest.fixture(scope="session")
def detail_body() -> bytes:
    return (FIXTURES / "mistercigar_detail.html").read_bytes()


async def test_first_ingestion_creates_brand_line_and_cigar(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body: bytes,
) -> None:
    use_case = IngestProductUrlUseCase(
        fetcher=_CannedFetcher(body=detail_body),
        parser=MistercigarProductParser(),
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        result = await use_case.execute(url=DETAIL_URL, uow=uow)

    assert result.outcome is IngestOutcome.CREATED
    assert result.cigar.full_name == "Vallejuelo Churchill"
    assert result.cigar.slug == "vallejuelo-vallejuelo-churchill"

    # Verify persistence: re-read in a fresh UoW
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        brand = await uow.brands.get_by_slug("vallejuelo")
        assert brand is not None
        assert brand.name == "Vallejuelo"

        cigar = await uow.cigars.get_by_slug(result.cigar.slug)
        assert cigar is not None
        assert cigar.length_mm is not None and int(cigar.length_mm) == 178
        assert cigar.ring_gauge == 47
        assert cigar.wrapper_country == "ECU"
        assert cigar.binder_country == "DOM"
        assert set(cigar.filler_countries) == {"NIC", "DOM"}
        assert len(cigar.blend_components) == 4


async def test_second_ingestion_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body: bytes,
) -> None:
    use_case = IngestProductUrlUseCase(
        fetcher=_CannedFetcher(body=detail_body),
        parser=MistercigarProductParser(),
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        first = await use_case.execute(url=DETAIL_URL, uow=uow)
    assert first.outcome is IngestOutcome.CREATED

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        second = await use_case.execute(url=DETAIL_URL, uow=uow)
    assert second.outcome is IngestOutcome.ALREADY_PRESENT
    assert second.cigar.id == first.cigar.id

    # No duplicate brand
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        assert await uow.brands.count() == 1
        assert await uow.cigars.count() == 1


async def test_ingestion_writes_source_record(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body: bytes,
) -> None:
    use_case = IngestProductUrlUseCase(
        fetcher=_CannedFetcher(body=detail_body),
        parser=MistercigarProductParser(),
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        result = await use_case.execute(url=DETAIL_URL, uow=uow)

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        records = await uow.source_records.find_for_cigar(result.cigar.id)

    assert len(records) == 1
    rec = records[0]
    assert rec.source_url == DETAIL_URL
    assert rec.source_domain == "mistercigar.com"
    assert rec.http_status == 200
    assert rec.raw_html_hash is not None and len(rec.raw_html_hash) == 64
    assert rec.parser_version == "mistercigar-1.0"
    assert rec.raw_payload is not None
    assert rec.raw_payload.get("brand_name") == "Vallejuelo"


async def test_ingestion_enqueues_primary_image_as_pending_media(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body: bytes,
) -> None:
    use_case = IngestProductUrlUseCase(
        fetcher=_CannedFetcher(body=detail_body),
        parser=MistercigarProductParser(),
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        result = await use_case.execute(url=DETAIL_URL, uow=uow)

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        media = await uow.media_assets.find_for_cigar(result.cigar.id)

    assert len(media) == 1
    asset = media[0]
    assert asset.is_primary is True
    assert asset.status.value == "pending"
    assert asset.original_url.startswith("https://mistercigar.com/wp-content/uploads/")
    assert asset.media_blob_hash is None  # not yet downloaded


async def test_re_ingest_does_not_duplicate_media(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body: bytes,
) -> None:
    use_case = IngestProductUrlUseCase(
        fetcher=_CannedFetcher(body=detail_body),
        parser=MistercigarProductParser(),
    )

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await use_case.execute(url=DETAIL_URL, uow=uow)

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await use_case.execute(url=DETAIL_URL, uow=uow)

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        cigar = await uow.cigars.get_by_slug("vallejuelo-vallejuelo-churchill")
        assert cigar is not None
        media = await uow.media_assets.find_for_cigar(cigar.id)
        records = await uow.source_records.find_for_cigar(cigar.id)

    assert len(media) == 1  # no duplicate media row
    assert len(records) == 2  # two fetch attempts → two audit rows
