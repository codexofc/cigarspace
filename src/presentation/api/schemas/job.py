# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Background job sub-resource schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from presentation.api.schemas.base import Links


class JobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(description="The arq job identifier.")
    status: Literal["queued", "in_progress", "complete", "failed", "unknown"]
    enqueued_at: float | None = Field(
        default=None,
        description="Unix timestamp when the job was queued.",
    )
    result: dict | None = Field(
        default=None,
        description="Job result body when status is `complete`.",
    )
    error: str | None = None
    links: Links = Field(alias="_links")


class MatchJobRequest(BaseModel):
    """Body of POST /api/v1/match-jobs."""

    model_config = ConfigDict(extra="forbid")

    scope: Literal["all", "cigar"]
    cigar_id: str | None = Field(
        default=None,
        description="UUID of the cigar (required when scope=cigar).",
    )
