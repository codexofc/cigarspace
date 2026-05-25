# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import date

import pytest

from infrastructure.customs._date_fr import parse_french_date


@pytest.mark.parametrize(
    "value,expected",
    [
        ("15 janvier 2026", date(2026, 1, 15)),
        ("1er février 2025", date(2025, 2, 1)),
        ("1ᵉʳ mars 2024", date(2024, 3, 1)),
        ("31 décembre 2023", date(2023, 12, 31)),
        ("4 décembre 2019", date(2019, 12, 4)),
        ("2 août 2019", date(2019, 8, 2)),
        # Without accents (some PDFs strip them)
        ("4 decembre 2019", date(2019, 12, 4)),
        ("2 aout 2019", date(2019, 8, 2)),
        # Mixed case
        ("4 Décembre 2019", date(2019, 12, 4)),
        # Embedded in text
        ("Arrêté du 4 décembre 2019 portant homologation", date(2019, 12, 4)),
    ],
)
def test_parses_valid_dates(value: str, expected: date) -> None:
    assert parse_french_date(value) == expected


def test_returns_none_on_invalid() -> None:
    assert parse_french_date(None) is None
    assert parse_french_date("") is None
    assert parse_french_date("nothing here") is None
    assert parse_french_date("32 janvier 2026") is None  # invalid day
    assert parse_french_date("4 marsi 2024") is None  # invalid month
