# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""SeedCustomsSourcesUseCase — UPSERT customs sources from a YAML file.

The YAML is the operator-managed source of truth for catalog (which
regulators exist, how to parse their indexes, default currency, etc.).
Runtime state (last_checked_at, …) lives in DB and is preserved on
re-seed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from domain.entities.customs import CustomsSource
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


@dataclass
class SeedReport:
    upserted: int = 0
    codes: list[str] = None  # type: ignore[assignment]


class SeedCustomsSourcesUseCase:
    def __init__(self) -> None:
        self._log = get_logger("usecase.seed_customs_sources")

    async def execute(self, *, yaml_path: Path, uow: SqlAlchemyUnitOfWork) -> SeedReport:
        with yaml_path.open(encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}

        sources_data: list[dict[str, Any]] = data.get("sources") or []
        report = SeedReport(codes=[])
        for raw in sources_data:
            source = CustomsSource(**raw)
            await uow.customs_sources.upsert(source)
            report.upserted += 1
            report.codes.append(source.code)

        await uow.commit()
        self._log.info("customs_seeded", count=report.upserted, codes=report.codes)
        return report
