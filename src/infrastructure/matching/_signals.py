# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Sub-scores for the hybrid matcher.

Each signal returns a value in ``[0, 1]``. They are independent of each other
and computed in pure Python so they can be unit-tested without spinning up
torch or pgvector.

The final ``score`` is a weighted blend, defined in
``infrastructure.matching.scorer.weighted_score``.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from infrastructure.matching._normalize import normalize


def exact_score(cigar_text: str, customs_text: str) -> float:
    """Asymmetric token-overlap score in ``[0, 1]``.

    The score is the share of the *shorter* token set that is shared with
    the other side. ``min(|A|, |B|)`` is the denominator on purpose: a
    customs label like "Toscanello" should fully match the merchant label
    "Toscano Toscano Toscanello Ammezzato Grappa" because every customs
    token is covered, even if the cigar carries more qualifiers.
    """
    cigar_norm = normalize(cigar_text)
    customs_norm = normalize(customs_text)
    if not cigar_norm or not customs_norm:
        return 0.0
    a = {t for t in cigar_norm.split() if len(t) >= 2}
    b = {t for t in customs_norm.split() if len(t) >= 2}
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    if overlap == 0:
        return 0.0
    return overlap / min(len(a), len(b))


def fuzzy_score(cigar_text: str, customs_text: str) -> float:
    """rapidfuzz token-set ratio normalized to [0, 1]."""
    cigar_norm = normalize(cigar_text)
    customs_norm = normalize(customs_text)
    if not cigar_norm or not customs_norm:
        return 0.0
    return fuzz.token_set_ratio(cigar_norm, customs_norm) / 100.0


def vector_score(cosine_distance: float) -> float:
    """Map a cosine distance returned by pgvector (``<=>``) into [0, 1]."""
    if cosine_distance is None:
        return 0.0
    # Cosine distance is in [0, 2] (0 = identical, 2 = opposite). For unit
    # vectors of mostly positive components it actually lives in [0, 1]; we
    # clamp defensively.
    return max(0.0, min(1.0, 1.0 - cosine_distance))


def pack_compat_score(
    expected_pack_size: int | None,
    candidate_pack_size: int | None,
) -> float:
    """Compatibility between the merchant-known pack_size and the candidate.

    The merchant often sells the same cigar in a box different from the
    customs nomenclature (cigares à l'unité chez le marchand, box of 5 ou 25
    côté douane). We never want pack_size mismatch to *kill* an otherwise
    strong match, so the floor is 0.2 rather than 0.

    - 1.0 when both are unknown OR exact match
    - 0.7 when one side is unknown (no signal, neutral)
    - 0.8 when ratio ≥ 0.8 (e.g. 20 vs 25)
    - 0.5 when ratio ≥ 0.5 (e.g. 10 vs 25)
    - 0.3 when ratio ≥ 0.2 (e.g. 5 vs 25, common case)
    - 0.2 otherwise
    """
    if expected_pack_size is None and candidate_pack_size is None:
        return 1.0
    if expected_pack_size is None or candidate_pack_size is None:
        return 0.7
    if expected_pack_size == candidate_pack_size:
        return 1.0
    ratio = min(expected_pack_size, candidate_pack_size) / max(
        expected_pack_size, candidate_pack_size
    )
    if ratio >= 0.8:
        return 0.8
    if ratio >= 0.5:
        return 0.5
    if ratio >= 0.2:
        return 0.3
    return 0.2
