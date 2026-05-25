# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

import json
from decimal import Decimal

from infrastructure.customs.extractors.legifrance_dila_json import (
    LegifranceDilaJsonExtractor,
)

_ARTICLE_HTML = """
<p>Arrêté du 4 décembre 2019, applicable à compter du 1er janvier 2020.</p>
<table>
  <thead>
    <tr><th>Marque</th><th>Désignation</th><th>Conditionnement</th><th>Prix (€)</th></tr>
  </thead>
  <tbody>
    <tr><td>COHIBA</td><td>Robusto</td><td>Boîte de 25 unités</td><td>18,50 €</td></tr>
    <tr><td>PADRON</td><td>1964 Anniversary</td><td>Boîte de 25 unités</td><td>22,00 €</td></tr>
  </tbody>
</table>
"""


def _dila_payload() -> bytes:
    """Synthesise a /consult/jorf JSON response with one article."""
    return json.dumps(
        {
            "id": "JORFTEXT000041534567",
            "articles": [
                {
                    "id": "ART1",
                    "texteHtml": _ARTICLE_HTML,
                }
            ],
        }
    ).encode("utf-8")


async def test_extracts_entries_from_json_payload() -> None:
    extractor = LegifranceDilaJsonExtractor()
    extractions = list(
        await extractor.extract(
            document_bytes=_dila_payload(),
            mime_type="application/json",
            default_currency="EUR",
            config={},
        )
    )
    assert len(extractions) == 2
    by_product = {x.raw_product_label: x for x in extractions}
    assert by_product["Robusto"].raw_brand_label == "COHIBA"
    assert by_product["Robusto"].unit_price == Decimal("18.50")
    assert by_product["1964 Anniversary"].unit_price == Decimal("22.00")


async def test_returns_empty_when_no_articles() -> None:
    extractor = LegifranceDilaJsonExtractor()
    extractions = list(
        await extractor.extract(
            document_bytes=b'{"id": "X", "articles": []}',
            mime_type="application/json",
            default_currency="EUR",
            config={},
        )
    )
    assert extractions == []


async def test_extracts_from_nested_articles() -> None:
    """DILA may nest articles inside sections; our walker should still
    find every node with `texteHtml`."""
    payload = json.dumps(
        {
            "id": "JORF",
            "sections": [
                {
                    "id": "S1",
                    "articles": [
                        {"id": "A1", "texteHtml": _ARTICLE_HTML},
                    ],
                }
            ],
        }
    ).encode("utf-8")
    extractor = LegifranceDilaJsonExtractor()
    extractions = list(
        await extractor.extract(
            document_bytes=payload,
            mime_type="application/json",
            default_currency="EUR",
            config={},
        )
    )
    assert len(extractions) == 2
