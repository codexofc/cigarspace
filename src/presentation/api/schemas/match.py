# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Cigar-customs match response + transition schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from domain.enums import Confidence, CustomsMatchStatus, MatchMethod
from presentation.api.schemas.base import Links


class MatchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    cigar_id: UUID
    customs_entry_id: UUID
    match_method: MatchMethod
    score: Decimal
    confidence: Confidence
    status: CustomsMatchStatus
    pack_size_bucket: int | None = None
    signals: dict[str, float] = Field(default_factory=dict)
    matched_at: datetime
    matched_by: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    links: Links = Field(alias="_links")


class MatchPatchRequest(BaseModel):
    """Body of ``PATCH /matches/{id}`` — human transition.

    Only HUMAN_* statuses are accepted; the matcher pipeline can set
    AUTO_* / PENDING_REVIEW programmatically but operators only flip
    pending matches into HUMAN_ACCEPTED / HUMAN_REJECTED through the API.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["human_accepted", "human_rejected"]
    notes: str | None = Field(default=None, max_length=1024)
