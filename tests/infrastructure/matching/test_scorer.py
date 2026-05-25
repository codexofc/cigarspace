# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import pytest

from domain.enums import Confidence, CustomsMatchStatus
from infrastructure.matching.scorer import (
    AUTO_ACCEPT_THRESHOLD,
    REVIEW_THRESHOLD,
    decide,
    quantize_score,
    weighted_score,
)


def test_weighted_score_uses_all_signals() -> None:
    signals = {"exact": 1.0, "fuzzy": 1.0, "vector": 1.0, "pack_compat": 1.0}
    assert weighted_score(signals) == pytest.approx(1.0)


def test_weighted_score_treats_missing_keys_as_zero() -> None:
    # Only exact present → its weight only
    assert weighted_score({"exact": 1.0}) == pytest.approx(0.40)


def test_decide_auto_accept_above_threshold() -> None:
    status, conf = decide(AUTO_ACCEPT_THRESHOLD + 0.01)
    assert status == CustomsMatchStatus.AUTO_ACCEPTED
    assert conf == Confidence.HIGH


def test_decide_review_zone() -> None:
    status, conf = decide(0.70)
    assert status == CustomsMatchStatus.PENDING_REVIEW
    assert conf == Confidence.MEDIUM


def test_decide_review_low_band() -> None:
    status, conf = decide(REVIEW_THRESHOLD + 0.01)
    assert status == CustomsMatchStatus.PENDING_REVIEW
    assert conf == Confidence.LOW


def test_decide_auto_reject() -> None:
    status, conf = decide(0.10)
    assert status == CustomsMatchStatus.AUTO_REJECTED
    assert conf == Confidence.LOW


def test_quantize_score_rounds_to_three_decimals() -> None:
    assert str(quantize_score(0.123456)) == "0.123"


def test_quantize_score_clamps_to_unit_range() -> None:
    assert str(quantize_score(-0.5)) == "0.000"
    assert str(quantize_score(1.5)) == "1.000"
