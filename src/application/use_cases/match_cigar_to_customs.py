# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""MatchCigarToCustomsUseCase — for one cigar, score and persist matches
against the customs price entries.

The pipeline is intentionally synchronous from the use case point of view —
the embedder (and the vector recall) are async I/O bound, but the scoring
loop is pure Python and runs over ~50 candidates per cigar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from application.ports.matching_repository import (
    CigarMatchingContext,
    CustomsCandidate,
)
from domain.entities.customs import CigarCustomsMatch
from domain.enums import CustomsMatchStatus, MatchMethod
from infrastructure.matching._normalize import customs_text as customs_norm
from infrastructure.matching._normalize import normalize
from infrastructure.matching._signals import (
    exact_score,
    fuzzy_score,
    pack_compat_score,
    vector_score,
)
from infrastructure.matching.scorer import (
    decide,
    quantize_score,
    weighted_score,
)
from infrastructure.observability.logging import get_logger
from infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

_MATCHER_VERSION = "matcher-v1.0+mpnet"


@dataclass
class MatchReport:
    cigar_id: str
    candidates_seen: int = 0
    matches_upserted: int = 0
    counts_by_status: dict[str, int] = field(default_factory=dict)
    error: str | None = None


class MatchCigarToCustomsUseCase:
    def __init__(self, *, top_k: int = 50) -> None:
        self._top_k = top_k
        self._log = get_logger("usecase.match_cigar_to_customs")

    async def execute(
        self,
        *,
        cigar_id: UUID,
        uow: SqlAlchemyUnitOfWork,
        country_code: str = "FR",
    ) -> MatchReport:
        report = MatchReport(cigar_id=str(cigar_id))

        ctx = await uow.matching.get_cigar_context(cigar_id)
        if ctx is None:
            report.error = "cigar_not_found"
            return report
        if ctx.embedding is None:
            report.error = "cigar_embedding_missing"
            return report

        candidates = await uow.matching.find_top_k_for_cigar(
            cigar_embedding=ctx.embedding,
            k=self._top_k,
            country_code=country_code,
        )
        report.candidates_seen = len(candidates)
        if not candidates:
            return report

        # Score each candidate, then bucket by pack_size and keep the best
        # candidate per bucket so the same cigar can carry one match per
        # commercial conditioning (à l'unité, en 5, en 10, en 25, …).
        cigar_label_norm = normalize(ctx.text)
        best_per_bucket: dict[int | None, tuple[float, dict, CustomsCandidate]] = {}
        for cand in candidates:
            signals = self._score_candidate(ctx, cand, cigar_label_norm)
            score = weighted_score(signals)
            bucket = cand.pack_size
            current = best_per_bucket.get(bucket)
            if current is None or score > current[0]:
                best_per_bucket[bucket] = (score, signals, cand)

        now = datetime.now(tz=UTC)
        for bucket, (score, signals, cand) in best_per_bucket.items():
            status, confidence = decide(score)
            if status == CustomsMatchStatus.AUTO_REJECTED:
                # Skip persisting rejections — keeps the table tight. The
                # signals are logged so we can tune later if needed.
                continue
            match = CigarCustomsMatch(
                cigar_id=cigar_id,
                customs_entry_id=cand.id,
                match_method=MatchMethod.HYBRID,
                score=quantize_score(score),
                confidence=confidence,
                status=status,
                pack_size_bucket=bucket,
                signals={k: round(v, 4) for k, v in signals.items()},
                matched_at=now,
                matched_by=_MATCHER_VERSION,
            )
            await uow.customs_matches.upsert(match)
            report.matches_upserted += 1
            report.counts_by_status[status.value] = report.counts_by_status.get(status.value, 0) + 1

        await uow.commit()
        self._log.info(
            "cigar_matched",
            cigar_id=str(cigar_id),
            candidates_seen=report.candidates_seen,
            upserted=report.matches_upserted,
            **report.counts_by_status,
        )
        return report

    def _score_candidate(
        self,
        ctx: CigarMatchingContext,
        cand: CustomsCandidate,
        cigar_label_norm: str,
    ) -> dict[str, float]:
        customs_label = customs_norm(cand.raw_brand_label, cand.raw_product_label)
        expected_pack = _pick_pack_size(ctx.pack_sizes, cand.pack_size)
        return {
            "exact": exact_score(cigar_label_norm, customs_label),
            "fuzzy": fuzzy_score(cigar_label_norm, customs_label),
            "vector": vector_score(cand.cosine_distance),
            "pack_compat": pack_compat_score(expected_pack, cand.pack_size),
        }


def _pick_pack_size(available: tuple[int, ...], candidate_size: int | None) -> int | None:
    """Return the cigar pack_size that best aligns with the candidate's.

    Picks an exact match if available, else the closest. With no packages
    known, returns None and pack_compat falls back to a neutral 0.7.
    """
    if not available:
        return None
    if candidate_size is None:
        # No candidate constraint: any of the cigar's known packs is fine.
        return available[0]
    if candidate_size in available:
        return candidate_size
    return min(available, key=lambda s: abs(s - candidate_size))
