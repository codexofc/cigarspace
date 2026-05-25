# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import pytest

from domain.services.slug import compose_slug, slugify


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cohiba Behike", "cohiba-behike"),
        ("Padrón 1964 Anniversary", "padron-1964-anniversary"),
        ("  HABANOS S.A.  ", "habanos-s-a"),
        ("Café/Crème — n°1", "cafe-creme-n1"),
        ("AB", "ab"),
        ("año 2024", "ano-2024"),
    ],
)
def test_slugify_roundtrip(text: str, expected: str) -> None:
    assert slugify(text) == expected


def test_slugify_rejects_empty() -> None:
    with pytest.raises(ValueError):
        slugify("")


def test_slugify_rejects_only_punctuation() -> None:
    with pytest.raises(ValueError):
        slugify("—///")


def test_slugify_truncates() -> None:
    long = "a" * 500
    assert len(slugify(long, max_length=64)) == 64


def test_compose_slug_joins_parts() -> None:
    assert compose_slug("Cohiba", "Behike", "BHK 52") == "cohiba-behike-bhk-52"


def test_compose_slug_skips_empty_parts() -> None:
    assert compose_slug("Cohiba", "", "Robusto") == "cohiba-robusto"
