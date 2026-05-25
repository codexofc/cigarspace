# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""PostgreSQL implementations of customs repositories (multi-country)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domain.entities.customs import (
    CigarCustomsMatch,
    CustomsPriceEntry,
    CustomsPublication,
    CustomsSource,
)
from domain.enums import CustomsMatchStatus, CustomsPublicationStatus
from infrastructure.persistence.mappers import (
    customs_match_to_domain,
    customs_match_to_model,
    customs_price_to_domain,
    customs_publication_to_domain,
    customs_source_to_domain,
)
from infrastructure.persistence.models import (
    CigarCustomsMatchModel,
    CustomsPriceEntryModel,
    CustomsPublicationModel,
    CustomsSourceModel,
)


# ---------------------------------------------------------------------------
# CustomsSource
# ---------------------------------------------------------------------------


class PgCustomsSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> CustomsSource | None:
        stmt = select(CustomsSourceModel).where(CustomsSourceModel.code == code)
        result = await self._session.execute(stmt)
        m = result.scalar_one_or_none()
        return customs_source_to_domain(m) if m else None

    async def get_by_id(self, source_id: UUID) -> CustomsSource | None:
        m = await self._session.get(CustomsSourceModel, source_id)
        return customs_source_to_domain(m) if m else None

    async def list_active(self) -> Sequence[CustomsSource]:
        stmt = (
            select(CustomsSourceModel)
            .where(CustomsSourceModel.is_active.is_(True))
            .order_by(CustomsSourceModel.country_code, CustomsSourceModel.code)
        )
        result = await self._session.execute(stmt)
        return [customs_source_to_domain(m) for m in result.scalars().all()]

    async def list_all(self) -> Sequence[CustomsSource]:
        stmt = select(CustomsSourceModel).order_by(
            CustomsSourceModel.country_code, CustomsSourceModel.code
        )
        result = await self._session.execute(stmt)
        return [customs_source_to_domain(m) for m in result.scalars().all()]

    async def upsert(self, source: CustomsSource) -> CustomsSource:
        """Idempotent upsert on `code` — used by the seed YAML loader.

        We do not touch the runtime state fields (last_checked_at,
        last_publication_seen_ref, consecutive_failures) on a re-seed —
        they belong to the worker, not the operator-managed seed file.
        """

        stmt = (
            pg_insert(CustomsSourceModel)
            .values(
                id=source.id,
                code=source.code,
                country_code=source.country_code,
                display_name=source.display_name,
                index_url=source.index_url,
                discovery_parser_name=source.discovery_parser_name,
                extraction_parser_name=source.extraction_parser_name,
                default_currency_code=source.default_currency_code,
                is_active=source.is_active,
                cron_expression=source.cron_expression,
                config_json=dict(source.config_json),
            )
            .on_conflict_do_update(
                index_elements=["code"],
                set_={
                    "country_code": source.country_code,
                    "display_name": source.display_name,
                    "index_url": source.index_url,
                    "discovery_parser_name": source.discovery_parser_name,
                    "extraction_parser_name": source.extraction_parser_name,
                    "default_currency_code": source.default_currency_code,
                    "is_active": source.is_active,
                    "cron_expression": source.cron_expression,
                    "config_json": dict(source.config_json),
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()
        result = await self.get_by_code(source.code)
        assert result is not None
        return result

    async def update_check_state(
        self,
        code: str,
        *,
        last_checked_at: datetime,
        last_publication_seen_ref: str | None = None,
        consecutive_failures: int | None = None,
    ) -> None:
        stmt = select(CustomsSourceModel).where(CustomsSourceModel.code == code)
        result = await self._session.execute(stmt)
        m = result.scalar_one()
        m.last_checked_at = last_checked_at
        if last_publication_seen_ref is not None:
            m.last_publication_seen_ref = last_publication_seen_ref
        if consecutive_failures is not None:
            m.consecutive_failures = consecutive_failures
        await self._session.flush()


# ---------------------------------------------------------------------------
# CustomsPublication
# ---------------------------------------------------------------------------


class PgCustomsPublicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, publication_id: UUID) -> CustomsPublication | None:
        m = await self._session.get(CustomsPublicationModel, publication_id)
        return customs_publication_to_domain(m) if m else None

    async def exists(self, source_id: UUID, regulator_reference: str) -> bool:
        stmt = select(CustomsPublicationModel.id).where(
            CustomsPublicationModel.source_id == source_id,
            CustomsPublicationModel.regulator_reference == regulator_reference,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def add(self, publication: CustomsPublication) -> CustomsPublication:
        stmt = (
            pg_insert(CustomsPublicationModel)
            .values(
                id=publication.id,
                source_id=publication.source_id,
                regulator_reference=publication.regulator_reference,
                publication_date=publication.publication_date,
                effective_date=publication.effective_date,
                document_url=publication.document_url,
                document_mime=publication.document_mime,
                content_hash=publication.content_hash,
                status=publication.status,
                fetched_at=publication.fetched_at,
                parsed_at=publication.parsed_at,
                failure_reason=publication.failure_reason,
                entries_count=publication.entries_count,
            )
            .on_conflict_do_nothing(index_elements=["source_id", "regulator_reference"])
            .returning(CustomsPublicationModel.id)
        )
        result = await self._session.execute(stmt)
        new_id = result.scalar_one_or_none()
        if new_id is None:
            # Lost the race — fetch existing
            stmt2 = select(CustomsPublicationModel).where(
                CustomsPublicationModel.source_id == publication.source_id,
                CustomsPublicationModel.regulator_reference == publication.regulator_reference,
            )
            r2 = await self._session.execute(stmt2)
            existing = r2.scalar_one()
            return customs_publication_to_domain(existing)
        await self._session.flush()
        created = await self._session.get(CustomsPublicationModel, new_id)
        assert created is not None
        return customs_publication_to_domain(created)

    async def mark_status(
        self,
        publication_id: UUID,
        *,
        status: CustomsPublicationStatus,
        failure_reason: str | None = None,
        entries_count: int | None = None,
        content_hash: str | None = None,
        fetched_at: datetime | None = None,
        parsed_at: datetime | None = None,
    ) -> CustomsPublication:
        m = await self._session.get(CustomsPublicationModel, publication_id)
        if m is None:
            raise LookupError(f"CustomsPublication {publication_id} not found")
        m.status = status
        if failure_reason is not None:
            m.failure_reason = failure_reason
        if entries_count is not None:
            m.entries_count = entries_count
        if content_hash is not None:
            m.content_hash = content_hash
        if fetched_at is not None:
            m.fetched_at = fetched_at
        if parsed_at is not None:
            m.parsed_at = parsed_at
        await self._session.flush()
        await self._session.refresh(m)
        return customs_publication_to_domain(m)

    async def list_by_source(
        self, source_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> Sequence[CustomsPublication]:
        from sqlalchemy import select as _select

        stmt = (
            _select(CustomsPublicationModel)
            .where(CustomsPublicationModel.source_id == source_id)
            .order_by(
                CustomsPublicationModel.publication_date.desc().nulls_last(),
                CustomsPublicationModel.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [customs_publication_to_domain(m) for m in result.scalars().all()]

    async def count_by_source(self, source_id: UUID) -> int:
        from sqlalchemy import func as _func, select as _select

        result = await self._session.execute(
            _select(_func.count())
            .select_from(CustomsPublicationModel)
            .where(CustomsPublicationModel.source_id == source_id)
        )
        return int(result.scalar_one())


# ---------------------------------------------------------------------------
# CustomsPriceEntry
# ---------------------------------------------------------------------------


class PgCustomsPriceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, entry: CustomsPriceEntry) -> CustomsPriceEntry:
        """Idempotent upsert on natural key.

        The natural key (publication_id, raw_brand_label, raw_product_label,
        packaging_description) is the same row coming from the same arrêté.
        Re-ingestion of the same publication updates the unit_price etc.
        but never duplicates.
        """

        # NB: packaging_description can be NULL — Postgres treats NULL as
        # NOT EQUAL to NULL in unique constraints, so we coalesce to '' for
        # the conflict check at app level by using empty string when None.
        packaging = entry.packaging_description or ""

        stmt = (
            pg_insert(CustomsPriceEntryModel)
            .values(
                id=entry.id,
                publication_id=entry.publication_id,
                country_code=entry.country_code,
                currency_code=entry.currency_code,
                unit_price=entry.unit_price,
                homologation_date=entry.homologation_date,
                effective_date=entry.effective_date,
                raw_brand_label=entry.raw_brand_label,
                raw_product_label=entry.raw_product_label,
                packaging_description=packaging or None,
                pack_size=entry.pack_size,
                unit_count=entry.unit_count,
                tax_class=entry.tax_class,
                extracted_at=entry.extracted_at,
                extractor_version=entry.extractor_version,
            )
            .on_conflict_do_update(
                index_elements=[
                    "publication_id",
                    "raw_brand_label",
                    "raw_product_label",
                    "packaging_description",
                ],
                set_={
                    "country_code": entry.country_code,
                    "currency_code": entry.currency_code,
                    "unit_price": entry.unit_price,
                    "homologation_date": entry.homologation_date,
                    "effective_date": entry.effective_date,
                    "pack_size": entry.pack_size,
                    "unit_count": entry.unit_count,
                    "tax_class": entry.tax_class,
                    "extracted_at": entry.extracted_at,
                    "extractor_version": entry.extractor_version,
                },
            )
            .returning(CustomsPriceEntryModel.id)
        )
        result = await self._session.execute(stmt)
        row_id = result.scalar_one()
        await self._session.flush()
        m = await self._session.get(CustomsPriceEntryModel, row_id)
        assert m is not None
        return customs_price_to_domain(m)

    async def get_by_id(self, entry_id: UUID) -> CustomsPriceEntry | None:
        m = await self._session.get(CustomsPriceEntryModel, entry_id)
        return customs_price_to_domain(m) if m else None

    async def find_by_publication(self, publication_id: UUID) -> Sequence[CustomsPriceEntry]:
        stmt = (
            select(CustomsPriceEntryModel)
            .where(CustomsPriceEntryModel.publication_id == publication_id)
            .order_by(
                CustomsPriceEntryModel.raw_brand_label,
                CustomsPriceEntryModel.raw_product_label,
            )
        )
        result = await self._session.execute(stmt)
        return [customs_price_to_domain(m) for m in result.scalars().all()]

    async def list_by_publication(
        self, publication_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> Sequence[CustomsPriceEntry]:
        stmt = (
            select(CustomsPriceEntryModel)
            .where(CustomsPriceEntryModel.publication_id == publication_id)
            .order_by(
                CustomsPriceEntryModel.raw_brand_label,
                CustomsPriceEntryModel.raw_product_label,
            )
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [customs_price_to_domain(m) for m in result.scalars().all()]

    async def count_by_publication(self, publication_id: UUID) -> int:
        from sqlalchemy import func as _func

        result = await self._session.execute(
            select(_func.count())
            .select_from(CustomsPriceEntryModel)
            .where(CustomsPriceEntryModel.publication_id == publication_id)
        )
        return int(result.scalar_one())

    async def find_by_label_and_country(
        self,
        country_code: str,
        raw_brand_label: str,
        raw_product_label: str,
    ) -> Sequence[CustomsPriceEntry]:
        stmt = (
            select(CustomsPriceEntryModel)
            .where(
                CustomsPriceEntryModel.country_code == country_code,
                CustomsPriceEntryModel.raw_brand_label == raw_brand_label,
                CustomsPriceEntryModel.raw_product_label == raw_product_label,
            )
            .order_by(CustomsPriceEntryModel.effective_date.desc())
        )
        result = await self._session.execute(stmt)
        return [customs_price_to_domain(m) for m in result.scalars().all()]

    async def find_by_effective_date(self, effective_date: date) -> Sequence[CustomsPriceEntry]:
        stmt = (
            select(CustomsPriceEntryModel)
            .where(CustomsPriceEntryModel.effective_date == effective_date)
            .order_by(CustomsPriceEntryModel.raw_brand_label)
        )
        result = await self._session.execute(stmt)
        return [customs_price_to_domain(m) for m in result.scalars().all()]


# ---------------------------------------------------------------------------
# CigarCustomsMatch (unchanged — kept country-neutral)
# ---------------------------------------------------------------------------


_HUMAN_LOCKED_STATUSES = (
    CustomsMatchStatus.HUMAN_ACCEPTED,
    CustomsMatchStatus.HUMAN_REJECTED,
)


class PgCigarCustomsMatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, match: CigarCustomsMatch) -> CigarCustomsMatch:
        m = customs_match_to_model(match)
        self._session.add(m)
        await self._session.flush()
        await self._session.refresh(m)
        return customs_match_to_domain(m)

    async def upsert(self, match: CigarCustomsMatch) -> CigarCustomsMatch:
        """Insert or refresh a match — but never overwrite a human verdict.

        The unique key is (cigar_id, customs_entry_id). If a row already
        exists with HUMAN_ACCEPTED / HUMAN_REJECTED, the upsert is a no-op
        on the conflicting row and we return the persisted entity untouched.
        """
        stmt = pg_insert(CigarCustomsMatchModel).values(
            id=match.id,
            cigar_id=match.cigar_id,
            customs_entry_id=match.customs_entry_id,
            match_method=match.match_method,
            score=match.score,
            confidence=match.confidence,
            status=match.status,
            pack_size_bucket=match.pack_size_bucket,
            signals=dict(match.signals or {}),
            matched_at=match.matched_at,
            matched_by=match.matched_by,
            reviewed_by=match.reviewed_by,
            reviewed_at=match.reviewed_at,
            notes=match.notes,
        )
        # Refresh everything but the human-locked status fields. The CASE
        # guard inside `set_` makes the UPDATE itself a no-op when a human
        # has already ruled on this pair.
        excluded = stmt.excluded
        human_locked = CigarCustomsMatchModel.status.in_(_HUMAN_LOCKED_STATUSES)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_cigar_customs_match_cigar_entry",
            set_={
                "match_method": excluded.match_method,
                "score": excluded.score,
                "confidence": excluded.confidence,
                "status": excluded.status,
                "pack_size_bucket": excluded.pack_size_bucket,
                "signals": excluded.signals,
                "matched_at": excluded.matched_at,
                "matched_by": excluded.matched_by,
            },
            where=~human_locked,
        ).returning(CigarCustomsMatchModel)

        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            # Human-locked row preserved — fetch and return as-is.
            stored = await self._session.execute(
                select(CigarCustomsMatchModel).where(
                    CigarCustomsMatchModel.cigar_id == match.cigar_id,
                    CigarCustomsMatchModel.customs_entry_id == match.customs_entry_id,
                )
            )
            row = stored.scalar_one()
        return customs_match_to_domain(row)

    async def get_by_id(self, match_id: UUID) -> CigarCustomsMatch | None:
        m = await self._session.get(CigarCustomsMatchModel, match_id)
        return customs_match_to_domain(m) if m else None

    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[CigarCustomsMatch]:
        stmt = select(CigarCustomsMatchModel).where(CigarCustomsMatchModel.cigar_id == cigar_id)
        result = await self._session.execute(stmt)
        return [customs_match_to_domain(m) for m in result.scalars().all()]

    async def find_for_entry(self, entry_id: UUID) -> Sequence[CigarCustomsMatch]:
        stmt = select(CigarCustomsMatchModel).where(
            CigarCustomsMatchModel.customs_entry_id == entry_id
        )
        result = await self._session.execute(stmt)
        return [customs_match_to_domain(m) for m in result.scalars().all()]

    async def list_by_statuses(
        self,
        statuses: Sequence[CustomsMatchStatus],
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CigarCustomsMatch]:
        stmt = (
            select(CigarCustomsMatchModel)
            .where(CigarCustomsMatchModel.status.in_(list(statuses)))
            .order_by(CigarCustomsMatchModel.score.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return [customs_match_to_domain(m) for m in result.scalars().all()]

    async def count_by_statuses(self, statuses: Sequence[CustomsMatchStatus]) -> int:
        from sqlalchemy import func as _func

        result = await self._session.execute(
            select(_func.count())
            .select_from(CigarCustomsMatchModel)
            .where(CigarCustomsMatchModel.status.in_(list(statuses)))
        )
        return int(result.scalar_one())

    async def count_by_status(self) -> dict[CustomsMatchStatus, int]:
        from sqlalchemy import func

        stmt = select(CigarCustomsMatchModel.status, func.count()).group_by(
            CigarCustomsMatchModel.status
        )
        result = await self._session.execute(stmt)
        return {status: count for status, count in result.all()}

    async def apply_human_decision(
        self,
        match_id: UUID,
        *,
        accepted: bool,
        reviewer: str,
        notes: str | None = None,
        when: datetime | None = None,
    ) -> CigarCustomsMatch:
        from datetime import timezone as _tz

        when = when or datetime.now(tz=_tz.utc)
        new_status = (
            CustomsMatchStatus.HUMAN_ACCEPTED if accepted else CustomsMatchStatus.HUMAN_REJECTED
        )
        m = await self._session.get(CigarCustomsMatchModel, match_id)
        if m is None:
            raise LookupError(f"CigarCustomsMatch {match_id} not found")
        m.status = new_status
        m.reviewed_by = reviewer
        m.reviewed_at = when
        if notes is not None:
            m.notes = notes
        await self._session.flush()
        await self._session.refresh(m)
        return customs_match_to_domain(m)
