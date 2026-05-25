# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Customs repository contracts — multi-country."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from domain.entities.customs import (
    CigarCustomsMatch,
    CustomsPriceEntry,
    CustomsPublication,
    CustomsSource,
)
from domain.enums import CustomsMatchStatus, CustomsPublicationStatus


class ICustomsSourceRepository(Protocol):
    async def get_by_code(self, code: str) -> CustomsSource | None: ...
    async def get_by_id(self, source_id: UUID) -> CustomsSource | None: ...
    async def list_active(self) -> Sequence[CustomsSource]: ...
    async def list_all(self) -> Sequence[CustomsSource]: ...
    async def upsert(self, source: CustomsSource) -> CustomsSource:
        """Idempotent upsert on `code`."""

    async def update_check_state(
        self,
        code: str,
        *,
        last_checked_at: datetime,
        last_publication_seen_ref: str | None = None,
        consecutive_failures: int | None = None,
    ) -> None: ...


class ICustomsPublicationRepository(Protocol):
    async def get_by_id(self, publication_id: UUID) -> CustomsPublication | None: ...
    async def exists(self, source_id: UUID, regulator_reference: str) -> bool: ...
    async def add(self, publication: CustomsPublication) -> CustomsPublication: ...
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
    ) -> CustomsPublication: ...

    async def list_by_source(
        self, source_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> Sequence[CustomsPublication]: ...
    async def count_by_source(self, source_id: UUID) -> int: ...


class ICustomsPriceRepository(Protocol):
    async def upsert(self, entry: CustomsPriceEntry) -> CustomsPriceEntry:
        """Idempotent insert on (publication_id, raw_brand_label,
        raw_product_label, packaging_description)."""

    async def get_by_id(self, entry_id: UUID) -> CustomsPriceEntry | None: ...
    async def find_by_publication(self, publication_id: UUID) -> Sequence[CustomsPriceEntry]: ...
    async def list_by_publication(
        self, publication_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> Sequence[CustomsPriceEntry]: ...
    async def count_by_publication(self, publication_id: UUID) -> int: ...
    async def find_by_label_and_country(
        self, country_code: str, raw_brand_label: str, raw_product_label: str
    ) -> Sequence[CustomsPriceEntry]: ...
    async def find_by_effective_date(self, effective_date: date) -> Sequence[CustomsPriceEntry]: ...


class ICigarCustomsMatchRepository(Protocol):
    async def add(self, match: CigarCustomsMatch) -> CigarCustomsMatch: ...
    async def upsert(self, match: CigarCustomsMatch) -> CigarCustomsMatch:
        """Insert or refresh on (cigar_id, customs_entry_id); HUMAN_* statuses
        are preserved untouched."""

    async def get_by_id(self, match_id: UUID) -> CigarCustomsMatch | None: ...
    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[CigarCustomsMatch]: ...
    async def find_for_entry(self, entry_id: UUID) -> Sequence[CigarCustomsMatch]: ...
    async def list_by_statuses(
        self,
        statuses: Sequence[CustomsMatchStatus],
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[CigarCustomsMatch]: ...
    async def count_by_statuses(self, statuses: Sequence[CustomsMatchStatus]) -> int: ...
    async def count_by_status(self) -> dict[CustomsMatchStatus, int]: ...
    async def apply_human_decision(
        self,
        match_id: UUID,
        *,
        accepted: bool,
        reviewer: str,
        notes: str | None = None,
        when: datetime | None = None,
    ) -> CigarCustomsMatch: ...
