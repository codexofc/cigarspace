# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""MediaBlob repository contract."""

from __future__ import annotations

from typing import Protocol

from domain.entities.media_blob import MediaBlob


class IMediaBlobRepository(Protocol):
    async def add(self, blob: MediaBlob) -> tuple[MediaBlob, bool]:
        """Insert a blob idempotently on content_hash.

        Returns (blob, was_inserted). was_inserted=False when an existing
        blob already had this hash — caller can skip the storage upload.
        """

    async def get_by_hash(self, content_hash: str) -> MediaBlob | None: ...
