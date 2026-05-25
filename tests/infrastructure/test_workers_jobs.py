# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Job-level tests — exercise the job functions directly with a mocked
ctx instead of running the full arq worker process. Integration since
the use case still hits the cigars_test database."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.fetcher import FetchRequest, FetchResponse
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from infrastructure.workers.jobs import (
    crawl_listing_job,
    ingest_product_job,
)

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parents[1] / "fixtures"
DETAIL_URL = "https://mistercigar.com/boutique/cigares/cigares-a-lunite/vallejuelo-churchill-1/"
LISTING_URL = "https://mistercigar.com/categorie-produit/cigares/cigares-a-lunite/"


class _CannedFetcher:
    """Maps {url: body} → FetchResponse. Used for both detail and listing pages."""

    def __init__(self, mapping: dict[str, bytes]) -> None:
        self._mapping = mapping

    async def fetch(self, request: FetchRequest) -> FetchResponse:
        body = self._mapping[request.url]
        return FetchResponse(
            url=request.url,
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            body=body,
            elapsed_s=0.01,
            fetched_at=datetime.now(tz=timezone.utc),
        )

    async def aclose(self) -> None:
        return None


class _RedisStub:
    """Records every enqueue_job call so tests can assert on them."""

    def __init__(self) -> None:
        self.enqueued: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    async def enqueue_job(self, name: str, *args: object, **kwargs: object) -> None:
        self.enqueued.append((name, args, kwargs))


def _ctx(
    fetcher: _CannedFetcher,
    session_factory: async_sessionmaker[AsyncSession],
    redis: _RedisStub | None = None,
) -> dict[str, object]:
    return {
        "fetcher": fetcher,
        "session_factory": session_factory,
        "redis": redis if redis is not None else _RedisStub(),
    }


@pytest.fixture(scope="session")
def detail_body() -> bytes:
    return (FIXTURES / "mistercigar_detail.html").read_bytes()


@pytest.fixture(scope="session")
def listing_body() -> bytes:
    return (FIXTURES / "mistercigar_listing.html").read_bytes()


# ---- ingest_product_job ---------------------------------------------------


async def test_ingest_product_job_persists_cigar(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    detail_body: bytes,
) -> None:
    fetcher = _CannedFetcher({DETAIL_URL: detail_body})
    ctx = _ctx(fetcher, session_factory)

    result = await ingest_product_job(ctx, DETAIL_URL)

    assert result["outcome"] == "created"
    assert "cigar_id" in result
    assert result["slug"] == "vallejuelo-vallejuelo-churchill"

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        cigar = await uow.cigars.get_by_slug(str(result["slug"]))
        assert cigar is not None


# ---- crawl_listing_job ----------------------------------------------------


async def test_crawl_listing_job_enqueues_product_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    listing_body: bytes,
) -> None:
    fetcher = _CannedFetcher({LISTING_URL: listing_body})
    redis = _RedisStub()
    ctx = _ctx(fetcher, session_factory, redis)

    report = await crawl_listing_job(ctx, LISTING_URL, max_pages=3, max_products=None)

    assert report["page_n"] == 1
    # The fixture has ~24 products + the post-fix pagination links to page 2,
    # so we expect 24 ingest_product_job + 1 crawl_listing_job follow-up.
    ingest_count = sum(1 for n, *_ in redis.enqueued if n == "ingest_product_job")
    crawl_count = sum(1 for n, *_ in redis.enqueued if n == "crawl_listing_job")
    assert ingest_count >= 20
    assert crawl_count == 1  # one follow-up page enqueued
    assert report["next_enqueued"] is True


async def test_crawl_listing_job_respects_max_products(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    listing_body: bytes,
) -> None:
    fetcher = _CannedFetcher({LISTING_URL: listing_body})
    redis = _RedisStub()
    ctx = _ctx(fetcher, session_factory, redis)

    report = await crawl_listing_job(ctx, LISTING_URL, max_pages=3, max_products=5)

    assert report.get("stop") == "max_products"
    assert sum(1 for n, *_ in redis.enqueued if n == "ingest_product_job") == 5
    # No follow-up crawl page enqueued
    assert not any(n == "crawl_listing_job" for n, *_ in redis.enqueued)


async def test_crawl_listing_job_stops_at_max_pages(
    session_factory: async_sessionmaker[AsyncSession],
    clean_db: None,
    listing_body: bytes,
) -> None:
    fetcher = _CannedFetcher({LISTING_URL: listing_body})
    redis = _RedisStub()
    ctx = _ctx(fetcher, session_factory, redis)

    # Pretend we're already on page 4 of a 3-page run
    report = await crawl_listing_job(ctx, LISTING_URL, max_pages=3, _page_n=4)

    assert report.get("stop") == "max_pages"
    assert redis.enqueued == []


# Note: download_media_job is exercised by tests/application/test_download_media_job.py
