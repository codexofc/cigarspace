# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Hybrid search response schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from presentation.api.schemas.cigar import CigarSummary


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cigar: CigarSummary
    score: float = Field(
        ge=0,
        description=(
            "Reciprocal Rank Fusion score: higher means the cigar surfaced "
            "near the top of more ranking branches."
        ),
    )
    matched_by: list[str] = Field(
        description=("Branches that surfaced this cigar — one of `full_text`, `vector`."),
        examples=[["full_text", "vector"]],
    )


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str
    items: list[SearchHit]
    total: int = Field(ge=0)
