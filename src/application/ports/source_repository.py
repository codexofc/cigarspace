# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""SourceRecord repository contract."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from domain.entities.tasting import SourceRecord


class ISourceRecordRepository(Protocol):
    async def add(self, record: SourceRecord) -> SourceRecord: ...
    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[SourceRecord]: ...
    async def find_by_url_hash(
        self, source_url: str, raw_html_hash: str
    ) -> SourceRecord | None: ...
