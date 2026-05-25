# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""RefreshCustomsSourceUseCase — scan a customs source's index and enqueue
new publications for ingestion.

Idempotent: re-running immediately yields zero new publications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from application.ports.fetcher import FetchError, FetchRequest, IFetcher
from application.services.customs_registry import CustomsRegistry
from domain.entities.customs import CustomsPublication
from domain.enums import CustomsPublicationStatus
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@dataclass
class RefreshReport:
    source_code: str
    total_seen: int = 0
    new_publications: int = 0
    new_publication_ids: list[str] = field(default_factory=list)
    error: str | None = None


class RefreshCustomsSourceUseCase:
    def __init__(self, *, fetcher: IFetcher) -> None:
        self._fetcher = fetcher
        self._log = get_logger("usecase.refresh_customs_source")

    async def execute(
        self,
        *,
        source_code: str,
        uow: SqlAlchemyUnitOfWork,
    ) -> RefreshReport:
        source = await uow.customs_sources.get_by_code(source_code)
        if source is None:
            return RefreshReport(source_code=source_code, error="source_not_found")
        if not source.is_active:
            return RefreshReport(source_code=source_code, error="source_inactive")
        if not source.index_url or source.index_url.lower() == "tbd":
            return RefreshReport(source_code=source_code, error="index_url_not_set")

        report = RefreshReport(source_code=source_code)
        adapter = CustomsRegistry.discovery(source.discovery_parser_name)

        # 1. Fetch index (skipped for API adapters that handle their own auth+verb)
        index_html = ""
        if getattr(adapter, "requires_index_fetch", True):
            try:
                response = await self._fetcher.fetch(
                    FetchRequest(url=source.index_url, timeout_s=30)
                )
                index_html = response.text
            except FetchError as exc:
                await uow.customs_sources.update_check_state(
                    source_code,
                    last_checked_at=datetime.now(tz=UTC),
                    consecutive_failures=source.consecutive_failures + 1,
                )
                await uow.commit()
                self._log.warning(
                    "customs_refresh_fetch_failed",
                    source=source_code,
                    error=str(exc),
                )
                report.error = f"fetch: {exc}"
                return report

        # 2. Discovery via registry
        discoveries = await adapter.find_publications(
            index_html=index_html,
            index_url=source.index_url,
            config=source.config_json,
        )
        report.total_seen = len(discoveries)

        # 3. Filter to new ones and persist + enqueue
        latest_ref_seen = source.last_publication_seen_ref
        for d in discoveries:
            existing = await uow.customs_publications.exists(source.id, d.regulator_reference)
            if existing:
                continue
            publication = CustomsPublication(
                source_id=source.id,
                regulator_reference=d.regulator_reference,
                document_url=d.document_url,
                document_mime=d.document_mime,
                publication_date=d.publication_date,
                effective_date=d.effective_date,
                status=CustomsPublicationStatus.DISCOVERED,
            )
            persisted = await uow.customs_publications.add(publication)
            report.new_publications += 1
            report.new_publication_ids.append(str(persisted.id))
            latest_ref_seen = d.regulator_reference

        await uow.customs_sources.update_check_state(
            source_code,
            last_checked_at=datetime.now(tz=UTC),
            last_publication_seen_ref=latest_ref_seen,
            consecutive_failures=0,
        )
        await uow.commit()

        self._log.info(
            "customs_refresh_done",
            source=source_code,
            total_seen=report.total_seen,
            new=report.new_publications,
        )
        return report
