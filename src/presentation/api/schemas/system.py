# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""System / health / version schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ComponentHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: Literal["ok", "degraded", "down"]
    detail: str | None = None


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded", "down"]
    checks: list[ComponentHealth]


class VersionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(examples=["0.1.0"])
    git_sha: str | None = Field(default=None, examples=["7ae5e23"])
    schema_head: str | None = Field(
        default=None,
        description="Current Alembic head revision.",
        examples=["be41166633b3"],
    )
