# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""HybridSearchUseCase — full-text + vector search fused by RRF.

Pipeline:
1. Normalise the query (accent strip, lowercase, punct collapse).
2. Full-text branch: pg_trgm similarity on cigar/brand names.
3. Vector branch: encode query with the shared embedder, recall top-K
   cigars by cosine distance via pgvector.
4. Fuse with Reciprocal Rank Fusion (k=60).
5. Return ordered hits with their fused score and the set of branches
   that surfaced them.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.embedder import IEmbedder
from domain.entities.cigar import Cigar
from infrastructure.matching._normalize import normalize
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork


_RRF_CONSTANT = 60


@dataclass(frozen=True)
class HybridHit:
    cigar: Cigar
    score: float
    matched_by: frozenset[str]


class HybridSearchUseCase:
    def __init__(self, *, embedder: IEmbedder) -> None:
        self._embedder = embedder

    async def execute(
        self,
        *,
        query: str,
        uow: SqlAlchemyUnitOfWork,
        limit: int = 20,
        recall_k: int = 50,
    ) -> list[HybridHit]:
        normalised = normalize(query)
        if not normalised:
            return []

        ft = await uow.matching.fulltext_search_cigars(query=normalised, k=recall_k)

        vec_hits: list = []
        try:
            embeddings = await self._embedder.encode([normalised])
        except Exception:
            embeddings = []
        if embeddings:
            vec_hits = list(
                await uow.matching.find_top_k_cigars_by_vector(
                    query_embedding=embeddings[0], k=recall_k
                )
            )

        scores: dict = {}
        for rank, (cid, _) in enumerate(ft):
            scores.setdefault(cid, {"score": 0.0, "matched_by": set()})
            scores[cid]["score"] += 1.0 / (_RRF_CONSTANT + rank + 1)
            scores[cid]["matched_by"].add("full_text")
        for rank, (cid, _) in enumerate(vec_hits):
            scores.setdefault(cid, {"score": 0.0, "matched_by": set()})
            scores[cid]["score"] += 1.0 / (_RRF_CONSTANT + rank + 1)
            scores[cid]["matched_by"].add("vector")

        ordered = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
        ordered = ordered[:limit]

        # Bulk-fetch the cigars referenced by the top results.
        hits: list[HybridHit] = []
        for cid, info in ordered:
            cigar = await uow.cigars.get_by_id(cid)
            if cigar is None:
                continue
            hits.append(
                HybridHit(
                    cigar=cigar,
                    score=round(info["score"], 6),
                    matched_by=frozenset(info["matched_by"]),
                )
            )
        return hits
