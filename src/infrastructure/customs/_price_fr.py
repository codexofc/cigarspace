# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Locale-aware French price parsing.

Handles:
- "12,50 €" / "12,50€" / "12,50 EUR"
- Non-breaking thousand separators U+00A0 and U+202F: "1 234,56 €"
- Whole numbers: "12 €", "12"
- Swiss formatting accepted too (CHF, apostrophe thousands optional)
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_NUMERIC_NOISE = re.compile(r"[\s   €$£¥CHFCHFcheueur’']", re.IGNORECASE)


def parse_price(text: str | None) -> Decimal | None:
    if not text:
        return None
    cleaned = _NUMERIC_NOISE.sub("", text).replace(",", ".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
