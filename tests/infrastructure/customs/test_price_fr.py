# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from decimal import Decimal

import pytest

from infrastructure.customs._price_fr import parse_price


@pytest.mark.parametrize(
    "value,expected",
    [
        ("12,50 €", Decimal("12.50")),
        ("12,50€", Decimal("12.50")),
        ("12,50 EUR", Decimal("12.50")),
        ("12 €", Decimal("12")),
        ("12", Decimal("12")),
        # Non-breaking thousand separators
        ("1 234,56 €", Decimal("1234.56")),
        ("1 234,56 €", Decimal("1234.56")),
        # Swiss CHF
        ("12.50 CHF", Decimal("12.50")),
        ("1'234.50 CHF", Decimal("1234.50")),
    ],
)
def test_parses_valid_prices(value: str, expected: Decimal) -> None:
    assert parse_price(value) == expected


def test_returns_none_on_invalid() -> None:
    assert parse_price(None) is None
    assert parse_price("") is None
    assert parse_price("not a price") is None
    assert parse_price("€") is None
