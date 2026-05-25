# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P

from infrastructure.customs.extractors.douane_ods import DouaneOdsExtractor


def _cell(value: str) -> TableCell:
    cell = TableCell()
    cell.addElement(P(text=value))
    return cell


def _row(values: list[str]) -> TableRow:
    row = TableRow()
    for v in values:
        row.addElement(_cell(v))
    return row


def _make_ods(rows: list[list[str]]) -> bytes:
    doc = OpenDocumentSpreadsheet()
    table = Table(name="Feuille1")
    for r in rows:
        table.addElement(_row(r))
    doc.spreadsheet.addElement(table)
    buf = BytesIO()
    doc.write(buf)
    return buf.getvalue()


_FIXTURE_ROWS: list[list[str]] = [
    [
        "Arrêté du 27 avril 2026, applicable à compter du 1er juin 2026, "
        "portant homologation des prix de vente au détail des tabacs manufacturés",
        "",
        "",
        "",
        "",
        "",
    ],
    ["", "", "", "", "", ""],
    ["DÉSIGNATION DES PRODUITS", "PRIX DE VENTE", "", "", "", ""],
    ["", "", "Anciens prix", "Anciens prix", "Nouveaux prix", "Nouveaux prix"],
    [
        "RÉFÉRENCE ACTUELLE",
        "NOUVEAU LIBELLÉ",
        "A l'unité",
        "Au conditionnement",
        "A l'unité",
        "Au conditionnement",
    ],
    ["FOURNISSEUR : LOGISTA France", "", "", "", "", ""],
    ["FABRICANT : BRITISH AMERICAN TOBACCO", "", "", "", "", ""],
    ["Cigares et cigarillos", "", "", "", "", ""],
    [
        "Lucky Strike Cigarillos, en 10 cigares",
        "",
        "0,70",
        "7,00",
        "Sans changement",
        "",
    ],
    [
        "Benson & Hedges Blue, en 20 unités",
        "",
        "",
        "11,00",
        "",
        "Sans changement",
    ],
    ["Tabacs à rouler", "", "", "", "", ""],
    [
        "Lucky Strike Original (blague), en 30 g",
        "",
        "",
        "18,50",
        "",
        "19,00",
    ],
    ["FABRICANT : PMI", "", "", "", "", ""],
    ["Cigarettes", "", "", "", "", ""],
    [
        "Marlboro Red, en 20 unités",
        "",
        "",
        "12,00",
        "",
        "12,50",
    ],
]


@pytest.fixture
def fixture_ods() -> bytes:
    return _make_ods(_FIXTURE_ROWS)


async def test_extracts_all_product_rows(fixture_ods: bytes) -> None:
    extractor = DouaneOdsExtractor()
    items = list(
        await extractor.extract(
            document_bytes=fixture_ods,
            mime_type="application/vnd.oasis.opendocument.spreadsheet",
            default_currency="EUR",
            config={},
        )
    )
    assert len(items) == 4


async def test_carries_current_fabricant_across_rows(fixture_ods: bytes) -> None:
    extractor = DouaneOdsExtractor()
    items = list(
        await extractor.extract(
            document_bytes=fixture_ods,
            mime_type="application/vnd.oasis.opendocument.spreadsheet",
            default_currency="EUR",
            config={},
        )
    )
    by_product = {x.raw_product_label: x for x in items}
    assert by_product["Lucky Strike Cigarillos"].raw_brand_label == "BRITISH AMERICAN TOBACCO"
    assert by_product["Marlboro Red"].raw_brand_label == "PMI"


async def test_falls_back_to_old_price_on_sans_changement(fixture_ods: bytes) -> None:
    extractor = DouaneOdsExtractor()
    items = list(
        await extractor.extract(
            document_bytes=fixture_ods,
            mime_type="application/vnd.oasis.opendocument.spreadsheet",
            default_currency="EUR",
            config={},
        )
    )
    by_product = {x.raw_product_label: x for x in items}
    # "Sans changement" → old price retained
    assert by_product["Lucky Strike Cigarillos"].unit_price == Decimal("7.00")
    assert by_product["Benson & Hedges Blue"].unit_price == Decimal("11.00")
    # Explicit new price used when given
    assert by_product["Lucky Strike Original (blague)"].unit_price == Decimal("19.00")
    assert by_product["Marlboro Red"].unit_price == Decimal("12.50")


async def test_extracts_pack_size_and_packaging(fixture_ods: bytes) -> None:
    extractor = DouaneOdsExtractor()
    items = list(
        await extractor.extract(
            document_bytes=fixture_ods,
            mime_type="application/vnd.oasis.opendocument.spreadsheet",
            default_currency="EUR",
            config={},
        )
    )
    by_product = {x.raw_product_label: x for x in items}
    cig = by_product["Lucky Strike Cigarillos"]
    assert cig.pack_size == 10
    assert cig.packaging_description == "en 10 cigares"
    rolled = by_product["Lucky Strike Original (blague)"]
    assert rolled.pack_size == 30
    assert rolled.packaging_description == "en 30 g"


async def test_extracts_dates(fixture_ods: bytes) -> None:
    extractor = DouaneOdsExtractor()
    items = list(
        await extractor.extract(
            document_bytes=fixture_ods,
            mime_type="application/vnd.oasis.opendocument.spreadsheet",
            default_currency="EUR",
            config={},
        )
    )
    # Every entry should carry the homologation/effective dates from the header.
    assert items, "extractor produced no items"
    for it in items:
        assert it.homologation_date == date(2026, 4, 27)
        assert it.effective_date == date(2026, 6, 1)


async def test_tax_class_carries_current_category(fixture_ods: bytes) -> None:
    extractor = DouaneOdsExtractor()
    items = list(
        await extractor.extract(
            document_bytes=fixture_ods,
            mime_type="application/vnd.oasis.opendocument.spreadsheet",
            default_currency="EUR",
            config={},
        )
    )
    by_product = {x.raw_product_label: x for x in items}
    assert by_product["Lucky Strike Cigarillos"].tax_class == "Cigares et cigarillos"
    assert by_product["Lucky Strike Original (blague)"].tax_class == "Tabacs à rouler"
    assert by_product["Marlboro Red"].tax_class == "Cigarettes"
