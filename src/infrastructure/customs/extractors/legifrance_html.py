# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Extract price entries from a Légifrance JORF arrêté (HTML form).

The arrêté typically contains one or several `<table>` blocks. Columns
encountered in practice:
    Marque | Désignation | Conditionnement | Prix de vente (€)
We detect the column order by header text rather than position.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, ClassVar

from selectolax.parser import HTMLParser, Node

from application.ports.customs_extractor import (
    CustomsPriceExtraction,
)
from infrastructure.customs._date_fr import parse_french_date
from infrastructure.customs._price_fr import parse_price

# Header keywords → canonical role
_HEADER_MAP: dict[str, str] = {
    "marque": "brand",
    "fabricant": "brand",
    "produit": "product",
    "désignation": "product",
    "designation": "product",
    "dénomination": "product",
    "denomination": "product",
    "conditionnement": "packaging",
    "packaging": "packaging",
    "présentation": "packaging",
    "prix": "price",
    "prix de vente": "price",
    "prix unitaire": "price",
    "tarif": "price",
    "pvd": "price",  # Prix de Vente au Détail
    "classe": "tax_class",
    "classe fiscale": "tax_class",
}


# Effective date patterns in the préambule
_EFFECTIVE_RE = re.compile(
    r"(?:applicable|en\s+vigueur|effet|effectives?)"
    r"(?:\s+(?:à\s+compter\s+du|le|au|du))?"
    r"\s+(\d{1,2}(?:er|ᵉʳ)?\s+[a-zéûôîà]+\s+\d{4})",
    re.IGNORECASE,
)
_DATE_DU_RE = re.compile(r"du\s+(\d{1,2}\s+[a-zéûôîà]+\s+\d{4})", re.IGNORECASE)
_PACK_SIZE_RE = re.compile(
    r"(?:bo[iî]te|paquet|conditionnement)?[^\d]*(\d+)\s*(?:unit|cigar|pi[èe]ce)", re.IGNORECASE
)


class LegifranceHtmlExtractor:
    name: ClassVar[str] = "legifrance-html"
    version: ClassVar[str] = "1.0"

    async def extract(
        self,
        *,
        document_bytes: bytes,
        mime_type: str,
        default_currency: str,
        config: dict[str, Any],
    ) -> Iterable[CustomsPriceExtraction]:
        html = document_bytes.decode("utf-8", errors="replace")
        tree = HTMLParser(html)

        # Dates from préambule (first 500 chars of body text)
        preamble = (tree.body.text(separator=" ") if tree.body else "")[:2000]
        homologation_date = _first_date(preamble, _DATE_DU_RE)
        effective_date = _first_date(preamble, _EFFECTIVE_RE) or homologation_date

        out: list[CustomsPriceExtraction] = []
        for table in tree.css("table"):
            columns = _detect_columns(table)
            if "price" not in columns or "product" not in columns:
                continue  # not a price table
            for row in _data_rows(table):
                cells = [_cell_text(td) for td in row.css("td")]
                if not cells:
                    continue
                try:
                    extraction = _build_extraction(
                        cells,
                        columns=columns,
                        homologation_date=homologation_date,
                        effective_date=effective_date,
                    )
                except _SkipRow:
                    continue
                if extraction is not None:
                    out.append(extraction)
        return out


# ---------------------------------------------------------------------------
# Helpers (private, module-level for testability)
# ---------------------------------------------------------------------------


class _SkipRow(Exception):
    """Internal flag to signal a row that should be silently dropped."""


def _cell_text(node: Node | None) -> str:
    if node is None:
        return ""
    text = node.text(separator=" ") or ""
    return re.sub(r"\s+", " ", text).strip()


def _detect_columns(table: Node) -> dict[str, int]:
    """Return a {role: column_index} mapping based on the first non-empty
    row that looks like a header (contains "Marque" / "Désignation" / …).
    Empty dict if no recognizable header."""

    rows = table.css("tr")
    for row in rows:
        ths = row.css("th")
        if ths:
            return _columns_from_cells(ths)
        # Some Légifrance tables use <td> as headers (no <th>) — first row
        # contains the keywords.
        tds = row.css("td")
        guessed = _columns_from_cells(tds)
        if "price" in guessed:
            return guessed
    return {}


def _columns_from_cells(cells: list[Node]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, c in enumerate(cells):
        key = _normalize_header(_cell_text(c))
        if key and key in _HEADER_MAP and _HEADER_MAP[key] not in out:
            out[_HEADER_MAP[key]] = i
    return out


def _normalize_header(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"\s*\(.+?\)\s*", "", t)  # drop "(EUR)" etc.
    t = re.sub(r"[\s\-_]+", " ", t).strip()
    return t


def _data_rows(table: Node) -> list[Node]:
    """Skip the header row(s); return rows that look like data."""
    rows = table.css("tr")
    data: list[Node] = []
    seen_header = False
    for row in rows:
        if not seen_header and (row.css("th") or _looks_like_header(row)):
            seen_header = True
            continue
        if not row.css("td"):
            continue
        data.append(row)
    return data


def _looks_like_header(row: Node) -> bool:
    cells = [_cell_text(td) for td in row.css("td")]
    if not cells:
        return False
    text = " ".join(cells).lower()
    return any(keyword in text for keyword in ("marque", "désignation", "designation", "prix"))


def _first_date(text: str, pattern: re.Pattern[str]) -> Any:
    m = pattern.search(text)
    return parse_french_date(m.group(1)) if m else None


def _build_extraction(
    cells: list[str],
    *,
    columns: dict[str, int],
    homologation_date: Any,
    effective_date: Any,
) -> CustomsPriceExtraction | None:
    brand_idx = columns.get("brand")
    product_idx = columns["product"]
    price_idx = columns["price"]
    pkg_idx = columns.get("packaging")
    tax_idx = columns.get("tax_class")

    max_idx = max(i for i in (brand_idx, product_idx, price_idx, pkg_idx, tax_idx) if i is not None)
    if max_idx >= len(cells):
        raise _SkipRow

    raw_brand = cells[brand_idx].strip() if brand_idx is not None else ""
    raw_product = cells[product_idx].strip()
    if not raw_product:
        raise _SkipRow

    price = parse_price(cells[price_idx])
    if price is None or price < 0:
        raise _SkipRow

    # Some Légifrance tables put brand & product together in one cell.
    if not raw_brand:
        # Split on first " — " or " - " or whitespace if no separator
        parts = re.split(r"\s+[–—-]\s+", raw_product, maxsplit=1)
        if len(parts) == 2:
            raw_brand, raw_product = parts[0].strip(), parts[1].strip()
        else:
            raw_brand = "UNKNOWN"

    packaging = cells[pkg_idx].strip() if pkg_idx is not None else None
    tax_class = cells[tax_idx].strip() if tax_idx is not None else None

    pack_size: int | None = None
    if packaging:
        m = _PACK_SIZE_RE.search(packaging)
        if m:
            try:
                pack_size = int(m.group(1))
            except ValueError:
                pass

    return CustomsPriceExtraction(
        raw_brand_label=raw_brand[:255],
        raw_product_label=raw_product[:255],
        packaging_description=packaging[:255] if packaging else None,
        unit_price=price,
        pack_size=pack_size,
        unit_count=None,
        tax_class=tax_class[:64] if tax_class else None,
        homologation_date=homologation_date,
        effective_date=effective_date,
    )
