# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Extract price entries from a DGDDI ``Maquette JORF`` ODS.

Layout observed across recent files (2024+):

    Row 0 : "Arrêté du DD mois YYYY, applicable …" — effective date.
    Row 1 : blank.
    Row 2-4 : multi-line table headers.
    Row 5+ : sections delimited by:
        FOURNISSEUR : <distributor>         (one or two per file)
        FABRICANT : <brand>                 (a few per fournisseur)
        <category text>                     (e.g. "Cigares et cigarillos")
        product rows                        (price cells in cols 2-5)

Columns (0-indexed) on product rows:
    0 : current label (with "en N cigares / unités / g")
    1 : new label (often blank — "no change")
    2 : Anciens À l'unité
    3 : Anciens Au conditionnement
    4 : Nouveaux À l'unité
    5 : Nouveaux Au conditionnement

We treat ``unit_price`` as the price at conditionnement (col 5, else col 3)
because that's the in-shop price; ``pack_size`` is parsed out of the label
so callers can derive the per-unit price as ``unit_price / pack_size``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, ClassVar

from application.ports.customs_extractor import (
    CustomsPriceExtraction,
)
from infrastructure.customs._date_fr import parse_french_date
from infrastructure.customs._ods import iter_rows
from infrastructure.customs._price_fr import parse_price

_PACK_RE = re.compile(
    r",\s*en\s+(\d+(?:[.,]\d+)?)\s*"
    r"(cigares?|cigarillos?|unit[ée]s?|pi[èe]ces?|paquets?|bo[iî]tes?|g|grammes?|ml)\b",
    re.IGNORECASE,
)
_ARRETE_DATE_RE = re.compile(
    r"Arr[êe]t[ée]\s+du\s+(\d{1,2}(?:er|ᵉʳ)?\s+[A-Za-zéûôîà]+\s+\d{4})",
    re.IGNORECASE,
)
_EFFECTIVE_RE = re.compile(
    r"applicable\s+(?:[^.]*?\b(?:à\s+compter\s+du|le|au))\s+"
    r"(\d{1,2}(?:er|ᵉʳ)?\s+[A-Za-zéûôîà]+\s+\d{4})",
    re.IGNORECASE,
)
_FOURNISSEUR_RE = re.compile(r"FOURNISSEUR\s*:\s*(.+)", re.IGNORECASE)
_FABRICANT_RE = re.compile(r"FABRICANT\s*:\s*(.+)", re.IGNORECASE)


class DouaneOdsExtractor:
    name: ClassVar[str] = "douane-ods"
    version: ClassVar[str] = "1.0"

    async def extract(
        self,
        *,
        document_bytes: bytes,
        mime_type: str,  # noqa: ARG002
        default_currency: str,  # noqa: ARG002 — kept for protocol compat
        config: dict[str, Any],  # noqa: ARG002
    ) -> Iterable[CustomsPriceExtraction]:
        out: list[CustomsPriceExtraction] = []

        homologation_date = None
        effective_date = None
        current_fabricant: str | None = None
        current_category: str | None = None
        seen_keys: set[tuple[str, str, str | None]] = set()

        for row in iter_rows(document_bytes):
            if not row:
                continue
            first = row[0].strip()
            if not first and not any(c for c in row[1:6]):
                continue  # blank row

            # Header section ("Arrêté du …")
            if homologation_date is None:
                m = _ARRETE_DATE_RE.search(first)
                if m:
                    homologation_date = parse_french_date(m.group(1))
            if effective_date is None:
                m = _EFFECTIVE_RE.search(first)
                if m:
                    effective_date = parse_french_date(m.group(1))

            m = _FOURNISSEUR_RE.match(first)
            if m:
                # Fournisseur change typically wipes the current brand
                # since brands belong to a manufacturer that belongs to
                # a distributor. We keep the fabricant intact for safety
                # and let the next FABRICANT row override it.
                continue

            m = _FABRICANT_RE.match(first)
            if m:
                current_fabricant = m.group(1).strip()
                current_category = None  # categories reset under each fabricant
                continue

            # Category line: a non-empty col 0 with everything else blank.
            if first and not any(c.strip() for c in row[1:6]):
                # Skip residual header repeats
                if first.upper().startswith(("RÉFÉRENCE", "DÉSIGNATION")):
                    continue
                current_category = first
                continue

            # Product row: pick the active conditionnement price.
            price = _select_price(row)
            if price is None or current_fabricant is None:
                continue

            label = (row[1].strip() or first) if len(row) > 1 else first
            pack_size, packaging = _split_packaging(label)
            product_name = _strip_packaging(label)

            key = (current_fabricant, product_name, packaging)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            out.append(
                CustomsPriceExtraction(
                    raw_brand_label=current_fabricant[:255],
                    raw_product_label=product_name[:255],
                    packaging_description=packaging,
                    unit_price=price,
                    pack_size=pack_size,
                    unit_count=None,
                    tax_class=current_category[:64] if current_category else None,
                    homologation_date=homologation_date,
                    effective_date=effective_date,
                )
            )

        return out


def _select_price(row: list[str]):
    # Prefer the new conditionnement price, fall back to the old one. Both
    # "unit" columns (2, 4) are kept for now in case we want them later.
    for idx in (5, 3):
        if idx >= len(row):
            continue
        cell = row[idx]
        if not cell or cell.strip().lower().startswith(("sans", "id.")):
            continue
        p = parse_price(cell)
        if p is not None:
            return p
    return None


def _split_packaging(label: str) -> tuple[int | None, str | None]:
    """Return (pack_size, packaging_description) from a label like
    ``"Lucky Strike Cigarillos, en 10 cigares"``."""
    m = _PACK_RE.search(label)
    if not m:
        return None, None
    raw_n = m.group(1).replace(",", ".")
    try:
        n = int(float(raw_n))
    except ValueError:
        n = None
    packaging = f"en {m.group(1)} {m.group(2).lower()}"
    return (n if n and n >= 1 else None), packaging


def _strip_packaging(label: str) -> str:
    return _PACK_RE.sub("", label).strip(" ,;:")
