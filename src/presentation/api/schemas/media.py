# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Media asset response schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import MediaAssetType, MediaStatus
from presentation.api.schemas.base import Links


class MediaAssetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    cigar_id: UUID
    asset_type: MediaAssetType
    original_url: str
    media_blob_hash: str | None = None
    is_primary: bool
    status: MediaStatus
    downloaded_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(
        alias="_links",
        description="Links include `self` and `download` (the pre-signed S3 URL).",
    )
