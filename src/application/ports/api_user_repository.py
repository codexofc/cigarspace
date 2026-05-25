# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""ApiUser repository contract."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.entities.api_user import ApiUser


class IApiUserRepository(Protocol):
    async def get_by_id(self, user_id: UUID) -> ApiUser | None: ...
    async def get_by_email(self, email: str) -> ApiUser | None: ...
    async def add(self, user: ApiUser) -> ApiUser: ...
    async def update_last_login(self, user_id: UUID, *, when: datetime) -> None: ...
    async def list_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[ApiUser]: ...
    async def count(self) -> int: ...
