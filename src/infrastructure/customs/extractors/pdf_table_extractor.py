# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Generic PDF table extractor — pdfplumber-backed.

Used as a fallback when the regulator publishes prices as a PDF rather
than HTML. Works on simple table layouts; the operator can tune via
`config_json`:

    {
      "header_keywords": ["Marque", "Prix"],   # used to detect header rows
      "min_columns": 3                          # ignore rows with fewer cells
    }
"""

from __future__ import annotations

import io
import re
from collections.abc import Iterable
from typing import Any, ClassVar

import pdfplumber

from application.ports.customs_extractor import (
    CustomsPriceExtraction,
    ICustomsExtractorAdapter,
)
from infrastructure.customs._date_fr import parse_french_date
from infrastructure.customs._price_fr import parse_price


_HEADER_MAP: dict[str, str] = {
    "marque": "brand",
    "fabricant": "brand",
    "produit": "product",
    "désignation": "product",
    "designation": "product",
    "conditionnement": "packaging",
    "packaging": "packaging",
    "prix": "price",
    "prix de vente": "price",
    "tarif": "price",
}


class PdfTableExtractor:
    name: ClassVar[str] = "pdf-table"
    version: ClassVar[str] = "1.0"

    async def extract(
        self,
        *,
        document_bytes: bytes,
        mime_type: str,
        default_currency: str,
        config: dict[str, Any],
    ) -> Iterable[CustomsPriceExtraction]:
        out: list[CustomsPriceExtraction] = []
        homologation_date = None
        effective_date = None

        with pdfplumber.open(io.BytesIO(document_bytes)) as pdf:
            # Dates from the first page's text
            if pdf.pages:
                first_text = pdf.pages[0].extract_text() or ""
                homologation_date = _first_date(first_text)
                effective_date = _first_effective(first_text) or homologation_date

            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    if not table:
                        continue
                    columns = _detect_columns(table[0])
                    if "price" not in columns or "product" not in columns:
                        continue
                    for row in table[1:]:
                        if not row:
                            continue
                        cells = [(c or "").strip() for c in row]
                        extraction = _build_extraction(
                            cells,
                            columns=columns,
                            homologation_date=homologation_date,
                            effective_date=effective_date,
                        )
                        if extraction is not None:
                            out.append(extraction)
        return out


def _detect_columns(header_row: list[str | None]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, raw in enumerate(header_row):
        key = (raw or "").lower().strip()
        key = re.sub(r"\s*\(.+?\)\s*", "", key)
        key = re.sub(r"[\s\-_]+", " ", key).strip()
        if key in _HEADER_MAP and _HEADER_MAP[key] not in out:
            out[_HEADER_MAP[key]] = i
    return out


_EFFECTIVE_RE = re.compile(
    r"(?:applicable|en vigueur|à compter du)\s+(\d{1,2}(?:er|ᵉʳ)?\s+[a-zéûôîà]+\s+\d{4})",
    re.IGNORECASE,
)
_DATE_DU_RE = re.compile(r"du\s+(\d{1,2}\s+[a-zéûôîà]+\s+\d{4})", re.IGNORECASE)


def _first_date(text: str) -> Any:
    m = _DATE_DU_RE.search(text)
    return parse_french_date(m.group(1)) if m else None


def _first_effective(text: str) -> Any:
    m = _EFFECTIVE_RE.search(text)
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

    max_idx = max(i for i in (brand_idx, product_idx, price_idx, pkg_idx) if i is not None)
    if max_idx >= len(cells):
        return None

    raw_product = cells[product_idx].strip()
    if not raw_product:
        return None
    price = parse_price(cells[price_idx])
    if price is None:
        return None

    raw_brand = (cells[brand_idx].strip() if brand_idx is not None else "") or "UNKNOWN"
    packaging = cells[pkg_idx].strip() if pkg_idx is not None else None

    return CustomsPriceExtraction(
        raw_brand_label=raw_brand[:255],
        raw_product_label=raw_product[:255],
        packaging_description=packaging[:255] if packaging else None,
        unit_price=price,
        homologation_date=homologation_date,
        effective_date=effective_date,
    )
