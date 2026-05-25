# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Generic repository protocol — narrow read/write contract."""

from __future__ import annotations

from typing import Protocol, TypeVar
from uuid import UUID

T = TypeVar("T")


class IRepository(Protocol[T]):
    """Minimal repository contract."""

    async def get(self, entity_id: UUID) -> T | None: ...
    async def add(self, entity: T) -> T: ...
    async def update(self, entity: T) -> T: ...
    async def delete(self, entity_id: UUID) -> bool: ...
