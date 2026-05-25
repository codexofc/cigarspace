# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Weighted blend of the matching signals + status decision.

Single source of truth for the four hyper-parameters that drive the
matching: ``WEIGHTS`` and the three confidence thresholds. Tunable in one
place, persisted in ``signals`` JSONB for audit.
"""

from __future__ import annotations

from decimal import Decimal

from domain.enums import Confidence, CustomsMatchStatus


# Tuning knobs — kept in code so they ship as a single artifact.
WEIGHTS: dict[str, float] = {
    "exact": 0.40,
    "fuzzy": 0.25,
    "vector": 0.25,
    "pack_compat": 0.10,
}

# Decision thresholds. Confidence enum tracks score quality (HIGH/MEDIUM/LOW)
# while CustomsMatchStatus tracks the workflow (auto-accept vs review queue).
AUTO_ACCEPT_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.50
HIGH_THRESHOLD = 0.85
MEDIUM_THRESHOLD = 0.65


def weighted_score(signals: dict[str, float]) -> float:
    """Blend signals with WEIGHTS; missing keys count as 0."""
    return sum(WEIGHTS[k] * signals.get(k, 0.0) for k in WEIGHTS)


def decide(score: float) -> tuple[CustomsMatchStatus, Confidence]:
    if score >= AUTO_ACCEPT_THRESHOLD:
        return CustomsMatchStatus.AUTO_ACCEPTED, Confidence.HIGH
    if score >= REVIEW_THRESHOLD:
        return CustomsMatchStatus.PENDING_REVIEW, (
            Confidence.HIGH
            if score >= HIGH_THRESHOLD
            else Confidence.MEDIUM
            if score >= MEDIUM_THRESHOLD
            else Confidence.LOW
        )
    return CustomsMatchStatus.AUTO_REJECTED, Confidence.LOW


def quantize_score(score: float) -> Decimal:
    """Round a float score to the persisted NUMERIC(4,3) precision."""
    return Decimal(f"{max(0.0, min(1.0, score)):.3f}")
