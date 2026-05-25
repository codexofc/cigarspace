# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""CigarPackage repository contract."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from domain.entities.cigar_package import CigarPackage


class ICigarPackageRepository(Protocol):
    async def add(self, package: CigarPackage) -> CigarPackage: ...
    async def update(self, package: CigarPackage) -> CigarPackage: ...
    async def find_by_cigar_and_url(
        self, cigar_id: UUID, source_url: str
    ) -> CigarPackage | None: ...
    async def find_for_cigar(self, cigar_id: UUID) -> Sequence[CigarPackage]: ...
