# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""MediaBlob entity — the unique physical content of an image.

One blob = one BLAKE3 hash = one object in the storage backend. Multiple
MediaAssets can point at the same blob (e.g. two cigars sharing a stock
photo), so the canonical media is keyed by `content_hash` rather than by
the merchant URL.

The storage backend is abstracted via IMediaStorage; the blob persists
the `storage_key` (e.g. "ab/abcdef….webp") not the absolute path/URL.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MediaBlob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_hash: str = Field(min_length=32, max_length=128)  # BLAKE3 hex
    storage_key: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=64)
    byte_size: int = Field(ge=1)
    width_px: int = Field(ge=1)
    height_px: int = Field(ge=1)

    first_seen_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
