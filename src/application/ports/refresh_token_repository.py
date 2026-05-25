# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""RefreshToken repository contract."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.entities.api_user import RefreshToken


class IRefreshTokenRepository(Protocol):
    async def add(self, token: RefreshToken) -> RefreshToken: ...
    async def find_by_hash(self, token_hash: str) -> RefreshToken | None: ...
    async def revoke(self, token_id: UUID, *, when: datetime) -> None: ...
    async def revoke_all_for_user(self, user_id: UUID, *, when: datetime) -> int:
        """Revoke every active refresh-token belonging to the user.
        Returns the number of rows updated."""
