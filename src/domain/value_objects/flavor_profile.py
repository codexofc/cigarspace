# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Flavor profile — 0..10 axis-based tasting representation."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FlavorProfile(BaseModel):
    """Aggregated tasting axes on a 0-10 scale (None = unknown)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    earthy: float | None = Field(default=None, ge=0, le=10)
    woody: float | None = Field(default=None, ge=0, le=10)
    cedar: float | None = Field(default=None, ge=0, le=10)
    spicy: float | None = Field(default=None, ge=0, le=10)
    pepper: float | None = Field(default=None, ge=0, le=10)
    sweet: float | None = Field(default=None, ge=0, le=10)
    floral: float | None = Field(default=None, ge=0, le=10)
    nutty: float | None = Field(default=None, ge=0, le=10)
    leather: float | None = Field(default=None, ge=0, le=10)
    coffee: float | None = Field(default=None, ge=0, le=10)
    chocolate: float | None = Field(default=None, ge=0, le=10)
    creamy: float | None = Field(default=None, ge=0, le=10)
    fruity: float | None = Field(default=None, ge=0, le=10)
    grassy: float | None = Field(default=None, ge=0, le=10)
    hay: float | None = Field(default=None, ge=0, le=10)

    def is_empty(self) -> bool:
        return all(v is None for v in self.model_dump().values())
