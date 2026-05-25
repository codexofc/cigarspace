# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""ApiUser response schema."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from presentation.api.schemas.base import Links


class UserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: EmailStr
    full_name: str | None = None
    is_active: bool
    is_admin: bool
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    links: Links = Field(alias="_links")
