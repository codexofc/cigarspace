# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""BuildEmbeddingsUseCase — populate the ``embedding`` column on cigars and
customs entries, in batches, idempotent.

The use case is the only place that knows how to chain "list pending rows
→ encode with IEmbedder → persist". It can target either side independently
so the operator can rebuild the customs embeddings without re-encoding the
12 k cigar rows (or vice-versa).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from application.ports.embedder import IEmbedder
from infrastructure.matching._normalize import customs_text, normalize
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


Target = Literal["cigar", "customs", "all"]


@dataclass
class BuildReport:
    target: Target
    encoded: int = 0
    batches: int = 0


class BuildEmbeddingsUseCase:
    def __init__(self, *, embedder: IEmbedder) -> None:
        self._embedder = embedder
        self._log = get_logger("usecase.build_embeddings")

    async def execute(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        target: Target = "all",
        batch_size: int = 256,
        max_batches: int | None = None,
    ) -> BuildReport:
        report = BuildReport(target=target)

        if target in ("cigar", "all"):
            await self._build_for_cigars(
                uow=uow, report=report, batch_size=batch_size, max_batches=max_batches
            )
        if target in ("customs", "all"):
            await self._build_for_customs(
                uow=uow, report=report, batch_size=batch_size, max_batches=max_batches
            )
        return report

    async def _build_for_cigars(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        report: BuildReport,
        batch_size: int,
        max_batches: int | None,
    ) -> None:
        while True:
            batch = await uow.matching.iter_cigars_without_embedding(limit=batch_size)
            if not batch:
                return
            texts = [normalize(job.text) for job in batch]
            vectors = await self._embedder.encode(texts)
            await uow.matching.set_cigar_embeddings(
                [(job.entity_id, vec) for job, vec in zip(batch, vectors)]
            )
            await uow.commit()
            report.encoded += len(batch)
            report.batches += 1
            self._log.info(
                "embeddings_batch_done",
                target="cigar",
                batch_size=len(batch),
                total=report.encoded,
            )
            if max_batches is not None and report.batches >= max_batches:
                return
            if len(batch) < batch_size:
                return

    async def _build_for_customs(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        report: BuildReport,
        batch_size: int,
        max_batches: int | None,
    ) -> None:
        # `iter_customs_without_embedding` already filters to tax_class LIKE
        # '%cigar%' so we skip the cigarette rows that don't need an embedding
        # for the cigar matching use case.
        while True:
            batch = await uow.matching.iter_customs_without_embedding(limit=batch_size)
            if not batch:
                return
            # Pre-normalize so the embedder sees the same surface form the
            # candidate scorer will compare against.
            texts = [customs_text("", job.text) for job in batch]
            vectors = await self._embedder.encode(texts)
            await uow.matching.set_customs_embeddings(
                [(job.entity_id, vec) for job, vec in zip(batch, vectors)]
            )
            await uow.commit()
            report.encoded += len(batch)
            report.batches += 1
            self._log.info(
                "embeddings_batch_done",
                target="customs",
                batch_size=len(batch),
                total=report.encoded,
            )
            if max_batches is not None and report.batches >= max_batches:
                return
            if len(batch) < batch_size:
                return
