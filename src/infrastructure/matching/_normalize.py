# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Text normalization for the matching pipeline.

The goal is to make the *raw* labels comparable without losing meaning:
strip diacritics, lowercase, collapse punctuation and whitespace, drop the
fabricant placeholders ("DIVERS LOGISTA", "DIVERS PIPAL") that pollute the
DGDDI feed without identifying anything.
"""

from __future__ import annotations

import re
import unicodedata

_DROP_BRAND_PREFIXES = ("divers ", "divers- ", "DIVERS ")
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    """ASCII-fold a Unicode string (NFD then drop combining marks)."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def normalize(text: str) -> str:
    """Lowercase + accent-strip + punct-strip + whitespace-collapse.

    The transform is idempotent: ``normalize(normalize(x)) == normalize(x)``.
    """
    if not text:
        return ""
    text = strip_accents(text).lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def normalize_brand(text: str) -> str:
    """Brand-aware normalize: drop the meaningless "DIVERS …" placeholders."""
    if not text:
        return ""
    for prefix in _DROP_BRAND_PREFIXES:
        if text.startswith(prefix):
            return ""
    return normalize(text)


def cigar_text(brand: str, line: str | None, name: str, vitole: str | None) -> str:
    """Build the canonical embedding string for a merchant-side Cigar."""
    parts = [brand, line or "", name, vitole or ""]
    return normalize(" ".join(p for p in parts if p))


def customs_text(raw_brand_label: str, raw_product_label: str) -> str:
    """Build the canonical embedding string for a customs entry."""
    brand = normalize_brand(raw_brand_label)
    product = normalize(raw_product_label)
    return f"{brand} {product}".strip() if brand else product
