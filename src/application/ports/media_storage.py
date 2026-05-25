# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Object storage port — S3-compatible API surface.

Implementations: SeaweedS3Storage (local sidecar) today, AwsS3Storage /
R2Storage tomorrow. The application layer never sees boto3 types.
"""

from __future__ import annotations

from typing import Protocol


class IMediaStorage(Protocol):
    async def put(
        self,
        *,
        content_hash: str,
        data: bytes,
        ext: str,
        mime_type: str,
    ) -> str:
        """Upload the blob. Returns the storage_key persisted on MediaBlob."""

    async def exists(self, *, storage_key: str) -> bool: ...

    async def public_url(self, *, storage_key: str) -> str:
        """URL a browser can GET directly (anonymous read allowed)."""

    async def aclose(self) -> None: ...
