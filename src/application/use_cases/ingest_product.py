# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""IngestProductUrlUseCase — fetch one product page → upsert Brand/Line/Cigar.

Flow:
    1. fetch(url)                      via IFetcher
    2. parse_product(html)             via IProductParser
    3. upsert brand                    via IBrandRepository
    4. upsert cigar line (from URL)    via ICigarLineRepository
    5. upsert cigar with blend         via ICigarRepository
    6. write a SourceRecord            via ISourceRecordRepository (audit)
    7. enqueue MediaAsset (PENDING)    via IMediaAssetRepository
    8. commit the UoW transaction

Idempotency:
    - Brand keyed by slug.
    - CigarLine keyed by (brand_id, slug). Slug inferred from URL path
      when present, fallback = brand_slug.
    - Cigar keyed by slug. Existing cigars are skipped (not overwritten);
      a separate UpdateCigar use case will land later for refresh.
    - SourceRecord is always written (one per fetch attempt for audit).
    - MediaAsset deduped by (cigar_id, original_url).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from application.ports.fetcher import FetchRequest, IFetcher
from application.ports.parser import IProductParser, ProductExtraction
from application.services.extraction_mapping import (
    brand_slug_from,
    build_cigar,
    build_cigar_components,
    resolve_line,
)
from domain.entities.brand import Brand
from domain.entities.cigar import Cigar
from domain.entities.cigar_line import CigarLine
from domain.entities.cigar_package import CigarPackage
from domain.entities.media import MediaAsset
from domain.entities.tasting import SourceRecord
from domain.enums import MediaAssetType, MediaStatus
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

# Parser/extractor version stamp persisted in SourceRecord for forward audit.
INGEST_PARSER_VERSION = "mistercigar-1.0"


class IngestOutcome(StrEnum):
    CREATED = "created"
    ALREADY_PRESENT = "already_present"


@dataclass(frozen=True)
class IngestResult:
    outcome: IngestOutcome
    cigar: Cigar
    extraction: ProductExtraction


def _blake2b_hex(data: bytes) -> str:
    return hashlib.blake2b(data, digest_size=32).hexdigest()


class IngestProductUrlUseCase:
    def __init__(
        self,
        *,
        fetcher: IFetcher,
        parser: IProductParser,
    ) -> None:
        self._fetcher = fetcher
        self._parser = parser
        self._log = get_logger("usecase.ingest_product")

    async def execute(
        self,
        *,
        url: str,
        uow: SqlAlchemyUnitOfWork,
    ) -> IngestResult:
        # 1. Fetch
        response = await self._fetcher.fetch(FetchRequest(url=url, timeout_s=30))

        # 2. Parse
        extraction = self._parser.parse_product(html=response.text, page_url=url)
        if not extraction.brand_name:
            raise ValueError(f"extraction missing brand_name for {url}")

        self._log.info(
            "extraction_ok",
            url=url,
            title=extraction.title,
            brand=extraction.brand_name,
            sku=extraction.sku,
        )

        # 3. Upsert brand
        brand_slug = brand_slug_from(extraction.brand_name)
        brand = await uow.brands.get_by_slug(brand_slug)
        if brand is None:
            brand = await uow.brands.add(
                Brand(
                    slug=brand_slug,
                    name=extraction.brand_name,
                    parent_company=extraction.manufacturer,
                )
            )
            self._log.info("brand_created", slug=brand_slug, name=extraction.brand_name)

        # 4. Upsert cigar line — inferred from the URL when present
        line_slug, line_name = resolve_line(url, brand.name, brand_slug)
        line = await uow.cigar_lines.get_by_slug(brand.id, line_slug)
        if line is None:
            line = await uow.cigar_lines.add(
                CigarLine(brand_id=brand.id, slug=line_slug, name=line_name)
            )
            self._log.info("cigar_line_created", brand=brand.name, slug=line_slug, name=line_name)

        # 5. Upsert cigar (skip on conflict — refresh handled by a separate use case)
        blend = build_cigar_components(extraction)
        cigar_to_create = build_cigar(extraction, line_id=line.id, blend_components=blend)

        existing = await uow.cigars.get_by_slug(cigar_to_create.slug)
        if existing is not None:
            cigar = existing
            outcome = IngestOutcome.ALREADY_PRESENT
        else:
            cigar = await uow.cigars.add(cigar_to_create)
            outcome = IngestOutcome.CREATED
            self._log.info(
                "cigar_created",
                slug=cigar.slug,
                brand=brand.name,
                vitola=cigar.vitola_name,
            )

        # 6. Audit trace — one SourceRecord per fetch attempt
        await uow.source_records.add(
            SourceRecord(
                cigar_id=cigar.id,
                source_domain=extraction.source_domain,
                source_url=url,
                http_status=response.status_code,
                fetched_at=response.fetched_at,
                raw_html_hash=_blake2b_hex(response.body),
                parser_version=INGEST_PARSER_VERSION,
                raw_payload=extraction.model_dump(mode="json", exclude_none=True),
            )
        )

        # 7. Upsert CigarPackage — packaging info attached to the canonical cigar.
        #    Only when pack_size is known; price/sku/last_seen_at refreshed
        #    on every re-ingest.
        if extraction.pack_size is not None:
            now = datetime.now(tz=UTC)
            existing_pkg = await uow.cigar_packages.find_by_cigar_and_url(cigar.id, url)
            if existing_pkg is None:
                await uow.cigar_packages.add(
                    CigarPackage(
                        cigar_id=cigar.id,
                        pack_size=extraction.pack_size,
                        source_domain=extraction.source_domain,
                        source_url=url,
                        sku=extraction.sku,
                        price_amount=extraction.price_amount,
                        price_currency=extraction.price_currency,
                        is_active=True,
                        last_seen_at=now,
                    )
                )
            else:
                # Refresh price/sku/last_seen_at
                refreshed = existing_pkg.model_copy(
                    update={
                        "pack_size": extraction.pack_size,
                        "sku": extraction.sku or existing_pkg.sku,
                        "price_amount": extraction.price_amount,
                        "price_currency": extraction.price_currency,
                        "is_active": True,
                        "last_seen_at": now,
                    }
                )
                await uow.cigar_packages.update(refreshed)

        # 8. Enqueue primary image as a PENDING MediaAsset ( will fetch/dedup)
        if extraction.primary_image_url:
            existing_media = await uow.media_assets.find_for_cigar_and_url(
                cigar.id, extraction.primary_image_url
            )
            if existing_media is None:
                await uow.media_assets.add(
                    MediaAsset(
                        cigar_id=cigar.id,
                        asset_type=MediaAssetType.FRONT,
                        original_url=extraction.primary_image_url,
                        is_primary=True,
                        status=MediaStatus.PENDING,
                    )
                )

        await uow.commit()
        return IngestResult(outcome=outcome, cigar=cigar, extraction=extraction)
