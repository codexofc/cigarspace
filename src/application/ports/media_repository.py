# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""MediaAsset repository contract."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from domain.entities.media import MediaAsset
from domain.enums import MediaStatus


class IMediaAssetRepository(Protocol):
    async def add(self, asset: MediaAsset) -> MediaAsset: ...
    async def get_by_id(self, asset_id: UUID) -> MediaAsset | None: ...
    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[MediaAsset]: ...
    async def find_for_cigar_and_url(
        self, cigar_id: UUID, original_url: str
    ) -> MediaAsset | None: ...
    async def find_pending(self, limit: int = 100) -> Sequence[MediaAsset]: ...
    async def mark_status(
        self,
        asset_id: UUID,
        *,
        status: MediaStatus,
        media_blob_hash: str | None = None,
    ) -> MediaAsset:
        """Update status (+ optionally link to a media_blob).

        downloaded_at is auto-stamped when status transitions to OK.
        """
