# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from domain.value_objects.dimensions import Dimensions
from domain.value_objects.flavor_profile import FlavorProfile


def test_dimensions_accepts_valid_measurements() -> None:
    d = Dimensions(
        length_mm=Decimal("125"),
        ring_gauge=52,
        ring_gauge_mm=Decimal("20.64"),
        weight_g=Decimal("12.3"),
    )
    assert d.length_mm == Decimal("125")
    assert d.ring_gauge == 52


def test_dimensions_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Dimensions(ring_gauge=100)  # > 80


def test_dimensions_is_frozen() -> None:
    d = Dimensions(length_mm=Decimal("125"))
    with pytest.raises(ValidationError):
        d.length_mm = Decimal("200")  # type: ignore[misc]


def test_dimensions_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        Dimensions(length_mm=Decimal("125"), foo="bar")  # type: ignore[call-arg]


def test_flavor_profile_default_is_empty() -> None:
    fp = FlavorProfile()
    assert fp.is_empty() is True


def test_flavor_profile_accepts_partial() -> None:
    fp = FlavorProfile(earthy=7.5, leather=6.0)
    assert fp.is_empty() is False
    assert fp.earthy == 7.5
    assert fp.leather == 6.0
    assert fp.sweet is None


def test_flavor_profile_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        FlavorProfile(earthy=11)


def test_flavor_profile_is_frozen() -> None:
    fp = FlavorProfile(earthy=5)
    with pytest.raises(ValidationError):
        fp.earthy = 10  # type: ignore[misc]
