# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Physical dimensions value object — immutable, validated."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Dimensions(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    length_mm: Decimal | None = Field(default=None, ge=0, le=500)
    ring_gauge: int | None = Field(default=None, ge=20, le=80)
    ring_gauge_mm: Decimal | None = Field(default=None, ge=0, le=50)
    weight_g: Decimal | None = Field(default=None, ge=0, le=500)
    draw_resistance_cmh2o: Decimal | None = Field(default=None, ge=0, le=500)
