# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""IngestCustomsPublicationUseCase — fetch one regulator document and
upsert the price entries it contains."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from application.ports.fetcher import FetchError, FetchRequest, IFetcher
from application.services.customs_registry import CustomsRegistry
from domain.entities.customs import CustomsPriceEntry
from domain.enums import CustomsPublicationStatus
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@dataclass
class IngestPublicationReport:
    publication_id: str
    status: str
    entries_inserted: int = 0
    error: str | None = None


def _blake2b_hex(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=32).hexdigest()


class IngestCustomsPublicationUseCase:
    def __init__(self, *, fetcher: IFetcher) -> None:
        self._fetcher = fetcher
        self._log = get_logger("usecase.ingest_customs_publication")

    async def execute(
        self,
        *,
        publication_id: UUID,
        uow: SqlAlchemyUnitOfWork,
    ) -> IngestPublicationReport:
        publication = await uow.customs_publications.get_by_id(publication_id)
        if publication is None:
            return IngestPublicationReport(
                publication_id=str(publication_id),
                status="not_found",
                error="publication_not_found",
            )

        source = await uow.customs_sources.get_by_id(publication.source_id)
        if source is None:
            return IngestPublicationReport(
                publication_id=str(publication_id),
                status="source_not_found",
                error=f"source {publication.source_id} not found",
            )

        extractor = CustomsRegistry.extractor(source.extraction_parser_name)

        # 1. Fetch — delegated to the extractor for API adapters (OAuth + POST).
        response_body: bytes
        response_mime: str
        if not getattr(extractor, "requires_document_fetch", True):
            try:
                response_body = await extractor.fetch_document(
                    document_url=publication.document_url,
                    config=source.config_json,
                )
            except Exception as exc:  # noqa: BLE001
                await uow.customs_publications.mark_status(
                    publication_id,
                    status=CustomsPublicationStatus.FAILED,
                    failure_reason=f"fetch: {exc}",
                    fetched_at=datetime.now(tz=timezone.utc),
                )
                await uow.commit()
                return IngestPublicationReport(
                    publication_id=str(publication_id),
                    status="fetch_failed",
                    error=str(exc),
                )
            response_mime = publication.document_mime or "application/json"
        else:
            try:
                response = await self._fetcher.fetch(
                    FetchRequest(url=publication.document_url, timeout_s=60)
                )
            except FetchError as exc:
                await uow.customs_publications.mark_status(
                    publication_id,
                    status=CustomsPublicationStatus.FAILED,
                    failure_reason=f"fetch: {exc}",
                    fetched_at=datetime.now(tz=timezone.utc),
                )
                await uow.commit()
                return IngestPublicationReport(
                    publication_id=str(publication_id),
                    status="fetch_failed",
                    error=str(exc),
                )
            response_body = response.body
            response_mime = publication.document_mime or response.headers.get(
                "content-type", "text/html"
            )

        new_hash = _blake2b_hex(response_body)

        # 2. SKIP if we already ingested the same content
        if publication.content_hash == new_hash:
            await uow.customs_publications.mark_status(
                publication_id,
                status=CustomsPublicationStatus.SKIPPED,
                fetched_at=datetime.now(tz=timezone.utc),
            )
            await uow.commit()
            return IngestPublicationReport(
                publication_id=str(publication_id),
                status="skipped_same_hash",
            )

        # 3. Extract
        try:
            extractions = list(
                await extractor.extract(
                    document_bytes=response_body,
                    mime_type=response_mime,
                    default_currency=source.default_currency_code,
                    config=source.config_json,
                )
            )
        except Exception as exc:  # noqa: BLE001
            await uow.customs_publications.mark_status(
                publication_id,
                status=CustomsPublicationStatus.FAILED,
                failure_reason=f"extract: {exc}",
                fetched_at=datetime.now(tz=timezone.utc),
                content_hash=new_hash,
            )
            await uow.commit()
            return IngestPublicationReport(
                publication_id=str(publication_id),
                status="extract_failed",
                error=str(exc),
            )

        # 4. UPSERT each entry on the natural key
        now = datetime.now(tz=timezone.utc)
        inserted = 0
        for x in extractions:
            entry = CustomsPriceEntry(
                publication_id=publication.id,
                country_code=source.country_code,
                currency_code=source.default_currency_code,
                unit_price=x.unit_price,
                homologation_date=x.homologation_date,
                effective_date=x.effective_date,
                raw_brand_label=x.raw_brand_label,
                raw_product_label=x.raw_product_label,
                packaging_description=x.packaging_description,
                pack_size=x.pack_size,
                unit_count=x.unit_count,
                tax_class=x.tax_class,
                extracted_at=now,
                extractor_version=f"{extractor.name}-{extractor.version}",
            )
            await uow.customs_prices.upsert(entry)
            inserted += 1

        await uow.customs_publications.mark_status(
            publication_id,
            status=CustomsPublicationStatus.INGESTED,
            content_hash=new_hash,
            entries_count=inserted,
            fetched_at=now,
            parsed_at=now,
        )
        await uow.commit()

        self._log.info(
            "customs_publication_ingested",
            publication=str(publication_id),
            entries=inserted,
            extractor=extractor.name,
        )
        return IngestPublicationReport(
            publication_id=str(publication_id),
            status="ingested",
            entries_inserted=inserted,
        )
