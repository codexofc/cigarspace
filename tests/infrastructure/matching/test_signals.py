# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import pytest

from infrastructure.matching._signals import (
    exact_score,
    fuzzy_score,
    pack_compat_score,
    vector_score,
)


def test_exact_score_full_token_subset() -> None:
    # All cigar tokens appear in the customs label → exact == 1.0
    assert exact_score("Cohiba Robusto", "Cohiba Robusto Tubos, en 25 unités") == 1.0


def test_exact_score_partial_overlap() -> None:
    # cigar {cohiba, behike} ∩ customs {cohiba, robusto} = {cohiba}
    # → overlap / min(len(a), len(b)) = 1/2 = 0.5
    assert exact_score("Cohiba Behike", "Cohiba Robusto") == 0.5


def test_exact_score_full_match_when_customs_subset() -> None:
    # All customs tokens covered by the cigar text → 1.0 (asymmetric)
    assert exact_score("Toscano Toscano Toscanello Ammezzato Grappa", "Toscanello") == 1.0


def test_exact_score_no_overlap() -> None:
    assert exact_score("Cohiba Behike", "Marlboro Red") == 0.0


def test_exact_score_ignores_short_tokens() -> None:
    # Single-char tokens are filtered out (set becomes {"Cohiba"} on the
    # cigar side, fully covered by "Cohiba Robusto") → 1.0
    assert exact_score("Cohiba 5", "Cohiba Robusto") == 1.0


def test_exact_score_empty() -> None:
    assert exact_score("", "anything") == 0.0
    assert exact_score("anything", "") == 0.0


def test_fuzzy_score_high_for_paraphrase() -> None:
    score = fuzzy_score("Cohiba Robusto Tubos", "Cohiba Robusto")
    assert score > 0.8


def test_fuzzy_score_low_for_unrelated() -> None:
    score = fuzzy_score("Cohiba Robusto", "Marlboro Red")
    assert score < 0.4


@pytest.mark.parametrize(
    "distance,expected_min,expected_max",
    [
        (0.0, 0.99, 1.0),
        (0.5, 0.49, 0.51),
        (1.0, 0.0, 0.01),
        (2.0, 0.0, 0.001),  # clamp
    ],
)
def test_vector_score_maps_cosine_distance(
    distance: float, expected_min: float, expected_max: float
) -> None:
    s = vector_score(distance)
    assert expected_min <= s <= expected_max


def test_pack_compat_exact_match() -> None:
    assert pack_compat_score(25, 25) == 1.0


def test_pack_compat_both_unknown() -> None:
    assert pack_compat_score(None, None) == 1.0


def test_pack_compat_one_unknown_is_neutral() -> None:
    assert pack_compat_score(None, 25) == 0.7
    assert pack_compat_score(25, None) == 0.7


def test_pack_compat_close_ratio() -> None:
    # 20 vs 25 → ratio 0.8 → high compat (not penalised)
    assert pack_compat_score(20, 25) == 0.8


def test_pack_compat_mid_ratio() -> None:
    # 10 vs 25 → ratio 0.4 → medium-low compat
    assert pack_compat_score(10, 25) == 0.3


def test_pack_compat_far_ratio_keeps_floor() -> None:
    # 5 vs 50 → ratio 0.1 → very low compat but non-zero (floor=0.2) so it
    # never zeroes out an otherwise good match.
    assert pack_compat_score(5, 50) == 0.2
