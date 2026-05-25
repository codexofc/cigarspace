# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Tasting notes & source provenance entities."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SourceRecord(BaseModel):
    """Provenance trace: when/where a piece of cigar data was extracted from."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    cigar_id: UUID | None = None
    source_domain: str = Field(min_length=1, max_length=255)
    source_url: str = Field(min_length=1, max_length=2048)
    http_status: int | None = Field(default=None, ge=100, le=599)
    fetched_at: datetime
    raw_html_hash: str | None = Field(default=None, max_length=128)
    parser_version: str | None = Field(default=None, max_length=64)
    extraction_confidence: Decimal | None = Field(default=None, ge=0, le=1)
    raw_payload: dict[str, Any] | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


class TastingNote(BaseModel):
    """A reviewer's tasting note for a cigar."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    cigar_id: UUID
    source_id: UUID | None = None
    reviewer_name: str | None = Field(default=None, max_length=255)
    published_at: datetime | None = None
    score: Decimal | None = Field(default=None, ge=0, le=100)
    score_scale: str | None = Field(default=None, max_length=64)
    notes_text: str | None = None
    notes_structured: dict[str, Any] | None = None
    pairing_recommendations: list[str] = Field(default_factory=list)

    created_at: datetime | None = None
    updated_at: datetime | None = None
