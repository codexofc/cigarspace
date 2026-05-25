# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import pytest

from infrastructure.matching._normalize import (
    cigar_text,
    customs_text,
    normalize,
    normalize_brand,
    strip_accents,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Cohíba", "Cohiba"),
        ("Padrón", "Padron"),
        ("Ñiño", "Nino"),
        ("français", "francais"),
        ("ALREADY ASCII", "ALREADY ASCII"),
    ],
)
def test_strip_accents(raw: str, expected: str) -> None:
    assert strip_accents(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Cohíba — Robusto (Tubo)  ", "cohiba robusto tubo"),
        ("Padrón 1964 N°5", "padron 1964 n 5"),
        ("", ""),
        ("    \t\n  ", ""),
        ("MIXED.case-Punct!", "mixed case punct"),
    ],
)
def test_normalize_idempotent_and_strips(raw: str, expected: str) -> None:
    assert normalize(raw) == expected
    # Idempotence
    assert normalize(normalize(raw)) == expected


def test_normalize_brand_drops_divers_placeholders() -> None:
    assert normalize_brand("DIVERS LOGISTA") == ""
    assert normalize_brand("DIVERS PIPAL") == ""
    assert normalize_brand("BRITISH AMERICAN TOBACCO") == "british american tobacco"


def test_cigar_text_combines_parts() -> None:
    out = cigar_text("Cohiba", "Behike", "BHK 56", "Robusto")
    assert "cohiba" in out and "behike" in out and "bhk 56" in out and "robusto" in out


def test_cigar_text_handles_missing_parts() -> None:
    assert cigar_text("Cohiba", None, "Robusto", None) == "cohiba robusto"


def test_customs_text_drops_meaningless_fabricant() -> None:
    # "DIVERS LOGISTA" carries no brand information; only the product remains
    assert customs_text("DIVERS LOGISTA", "Cohiba Robusto") == "cohiba robusto"


def test_customs_text_keeps_real_fabricant() -> None:
    assert customs_text("PMI", "Marlboro Red, en 20 unités").startswith("pmi marlboro")
