# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""MediaAsset entity — the link between a Cigar and a MediaBlob.

Physical attributes of the image (path, hash, dimensions, mime) now live
on MediaBlob (one row per unique content). MediaAsset captures the
semantic role of the image for a given cigar:
- asset_type (FRONT, BAND, BOX_*, LIFESTYLE, ASH, …)
- is_primary
- status (PENDING → OK / FAILED / QUARANTINED)
- original_url (audit: where we found it)
- media_blob_hash (None until the worker downloads & validates the file)
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import MediaAssetType, MediaStatus


class MediaAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    cigar_id: UUID
    asset_type: MediaAssetType
    original_url: str = Field(min_length=1, max_length=2048)

    media_blob_hash: str | None = Field(default=None, max_length=128)

    is_primary: bool = False
    status: MediaStatus = MediaStatus.PENDING
    downloaded_at: datetime | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None
