# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from domain.entities.brand import Brand
from domain.entities.cigar import BlendComponent, Cigar
from domain.entities.cigar_line import CigarLine
from domain.entities.customs import CigarCustomsMatch, CustomsPriceEntry
from domain.enums import (
    BlendComponentType,
    Confidence,
    FormatCategory,
    Intensity,
    MatchMethod,
)


def test_brand_minimal_valid() -> None:
    b = Brand(slug="cohiba", name="Cohiba")
    assert b.slug == "cohiba"
    assert b.is_active is True
    assert b.aliases == []


def test_brand_rejects_invalid_slug() -> None:
    with pytest.raises(ValidationError):
        Brand(slug="Cohiba Cigar", name="Cohiba")  # uppercase + space


def test_brand_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Brand(slug="cohiba", name="Cohiba", color="red")  # type: ignore[call-arg]


def test_cigar_line_requires_brand_id() -> None:
    with pytest.raises(ValidationError):
        CigarLine(slug="behike", name="Behike")  # type: ignore[call-arg]


def test_cigar_minimal_valid() -> None:
    line_id = uuid4()
    c = Cigar(
        line_id=line_id,
        slug="cohiba-behike-bhk-52",
        full_name="Cohiba Behike BHK 52",
        vitola_name="BHK 52",
        format_category=FormatCategory.ROBUSTO,
    )
    assert c.line_id == line_id
    assert c.format_category is FormatCategory.ROBUSTO
    assert c.flavor_profile.is_empty()
    assert c.is_handmade is True
    assert c.is_cuban is False


def test_cigar_accepts_blend_components() -> None:
    line_id = uuid4()
    c = Cigar(
        line_id=line_id,
        slug="cohiba-robusto",
        full_name="Cohiba Robusto",
        vitola_name="Robusto",
        strength=Intensity.MEDIUM_FULL,
        body=Intensity.MEDIUM,
        blend_components=[
            BlendComponent(
                component_type=BlendComponentType.WRAPPER,
                tobacco_origin="CUB",
                source_confidence=Confidence.HIGH,
            ),
            BlendComponent(
                component_type=BlendComponentType.FILLER_LIGERO,
                tobacco_origin="CUB",
                percentage=Decimal("20"),
                source_confidence=Confidence.MEDIUM,
            ),
        ],
    )
    assert len(c.blend_components) == 2
    assert c.blend_components[0].component_type is BlendComponentType.WRAPPER


def test_customs_price_entry_requires_publication() -> None:
    """publication_id is the mandatory link to a CustomsPublication."""
    with pytest.raises(ValidationError):
        CustomsPriceEntry(  # type: ignore[call-arg]
            country_code="FR",
            currency_code="EUR",
            unit_price=Decimal("18.50"),
            raw_brand_label="COHIBA",
            raw_product_label="ROBUSTO",
            extracted_at=datetime(2024, 3, 1, tzinfo=UTC),
            extractor_version="legifrance-html-1.0",
        )


def test_customs_match_requires_score_in_range() -> None:
    with pytest.raises(ValidationError):
        CigarCustomsMatch(
            cigar_id=uuid4(),
            customs_entry_id=uuid4(),
            match_method=MatchMethod.EXACT,
            score=Decimal("1.5"),  # > 1.0
            confidence=Confidence.HIGH,
            matched_at=datetime(2024, 3, 1, tzinfo=UTC),
            matched_by="system",
        )


def test_customs_entry_full() -> None:
    e = CustomsPriceEntry(
        publication_id=uuid4(),
        country_code="FR",
        currency_code="EUR",
        unit_price=Decimal("18.50"),
        homologation_date=date(2024, 3, 1),
        effective_date=date(2024, 4, 1),
        raw_brand_label="COHIBA",
        raw_product_label="ROBUSTO",
        pack_size=25,
        extracted_at=datetime(2024, 3, 1, tzinfo=UTC),
        extractor_version="legifrance-html-1.0",
    )
    assert e.unit_price == Decimal("18.50")
    assert e.currency_code == "EUR"
    assert e.country_code == "FR"
    assert e.pack_size == 25
