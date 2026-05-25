# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from infrastructure.customs.extractors.legifrance_html import (
    LegifranceHtmlExtractor,
)

FIXTURE = Path(__file__).parents[2] / "fixtures" / "customs" / "legifrance_arrete_synthetic.html"


async def test_extracts_all_rows() -> None:
    body = FIXTURE.read_bytes()
    extractor = LegifranceHtmlExtractor()
    extractions = list(
        await extractor.extract(
            document_bytes=body,
            mime_type="text/html",
            default_currency="EUR",
            config={},
        )
    )
    assert len(extractions) == 4


async def test_parses_brand_product_and_price() -> None:
    body = FIXTURE.read_bytes()
    extractions = list(
        await LegifranceHtmlExtractor().extract(
            document_bytes=body,
            mime_type="text/html",
            default_currency="EUR",
            config={},
        )
    )
    by_product = {x.raw_product_label: x for x in extractions}

    behike = by_product["Behike BHK 52"]
    assert behike.raw_brand_label == "COHIBA"
    assert behike.unit_price == Decimal("185.00")
    assert behike.packaging_description == "Boîte de 10 unités"
    assert behike.pack_size == 10

    robusto = by_product["Robusto"]
    assert robusto.unit_price == Decimal("18.50")
    assert robusto.pack_size == 25


async def test_parses_dates_from_preamble() -> None:
    body = FIXTURE.read_bytes()
    extractions = list(
        await LegifranceHtmlExtractor().extract(
            document_bytes=body,
            mime_type="text/html",
            default_currency="EUR",
            config={},
        )
    )
    # All rows should share the dates derived from the préambule
    for x in extractions:
        assert x.homologation_date == date(2019, 12, 4)
        assert x.effective_date == date(2020, 1, 1)


async def test_handles_non_breaking_space_in_price() -> None:
    body = FIXTURE.read_bytes()
    extractions = list(
        await LegifranceHtmlExtractor().extract(
            document_bytes=body,
            mime_type="text/html",
            default_currency="EUR",
            config={},
        )
    )
    by_product = {x.raw_product_label: x for x in extractions}
    monte = by_product["No. 2"]
    assert monte.raw_brand_label == "MONTECRISTO"
    assert monte.unit_price == Decimal("1234.56")
