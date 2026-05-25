# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CrawlListingUseCase — walk a category listing and ingest every product.

Iterates pages via the listing parser's next_page_url. For each product
URL on each page, runs IngestProductUrlUseCase. Stops at max_pages or
when there is no next page.

Per-URL failures are logged and counted but do not abort the run; the
overall result tallies created / already_present / failed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from application.ports.fetcher import FetchError, FetchRequest, IFetcher
from application.ports.parser import IListingParser, IProductParser
from application.use_cases.ingest_product import (
    IngestOutcome,
    IngestProductUrlUseCase,
)
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass
class CrawlReport:
    pages_visited: int = 0
    products_seen: int = 0
    created: int = 0
    already_present: int = 0
    failed: int = 0
    errors: list[tuple[str, str]] = field(default_factory=list)  # (url, message)


class CrawlListingUseCase:
    def __init__(
        self,
        *,
        fetcher: IFetcher,
        listing_parser: IListingParser,
        product_parser: IProductParser,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._fetcher = fetcher
        self._listing_parser = listing_parser
        self._product_parser = product_parser
        self._session_factory = session_factory
        self._ingest = IngestProductUrlUseCase(fetcher=fetcher, parser=product_parser)
        self._log = get_logger("usecase.crawl_listing")

    async def execute(
        self,
        *,
        start_url: str,
        max_pages: int = 5,
        max_products: int | None = None,
    ) -> CrawlReport:
        report = CrawlReport()
        current_url: str | None = start_url

        while current_url and report.pages_visited < max_pages:
            self._log.info("page_fetch", url=current_url, n=report.pages_visited + 1)
            response = await self._fetcher.fetch(FetchRequest(url=current_url, timeout_s=30))
            listing = self._listing_parser.parse_listing(html=response.text, page_url=current_url)
            report.pages_visited += 1
            report.products_seen += len(listing.product_urls)

            for product_url in listing.product_urls:
                if (
                    max_products is not None
                    and (report.created + report.already_present + report.failed) >= max_products
                ):
                    self._log.info("max_products_reached")
                    return report

                try:
                    async with SqlAlchemyUnitOfWork(self._session_factory) as uow:
                        result = await self._ingest.execute(url=product_url, uow=uow)
                    if result.outcome is IngestOutcome.CREATED:
                        report.created += 1
                    else:
                        report.already_present += 1
                except FetchError as exc:
                    report.failed += 1
                    report.errors.append((product_url, f"fetch: {exc}"))
                    self._log.warning("product_fetch_failed", url=product_url, error=str(exc))
                except Exception as exc:  # noqa: BLE001
                    report.failed += 1
                    report.errors.append((product_url, f"{type(exc).__name__}: {exc}"))
                    self._log.error(
                        "product_ingest_failed",
                        url=product_url,
                        error=str(exc),
                        exc_type=type(exc).__name__,
                    )

            current_url = listing.next_page_url

        return report
