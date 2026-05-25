# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""API user + refresh-token domain entities.

The domain stays free of HTTP concerns: passwords are stored as opaque
strings (hashed elsewhere by the presentation layer), refresh tokens are
stored as opaque hashes (sha256 of the random opaque secret). The domain
only models what the database persists.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApiUser(BaseModel):
    """A human (or service account) authenticated against the public API."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)
    password_hash: str = Field(min_length=1, max_length=512)
    is_active: bool = True
    is_admin: bool = False
    last_login_at: datetime | None = None

    created_at: datetime | None = None
    updated_at: datetime | None = None


class RefreshToken(BaseModel):
    """An opaque refresh-token whose plain value is only known at issuance."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    token_hash: str = Field(min_length=64, max_length=64)  # hex sha256
    expires_at: datetime
    revoked_at: datetime | None = None
    user_agent: str | None = None
    ip_address: str | None = Field(default=None, max_length=64)

    created_at: datetime | None = None
