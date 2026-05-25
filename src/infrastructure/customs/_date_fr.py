# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""French date parsing utilities (no dateutil dep).

Handles "15 janvier 2026", "1er février 2025", uppercase variants.
Returns None when the string can't be parsed (caller decides what to do).
"""

from __future__ import annotations

import re
from datetime import date

MOIS_FR: dict[str, int] = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

# "15 janvier 2026" or "1er février 2025" or "1ᵉʳ février 2025"
_FR_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\s*(?:er|ᵉʳ|e)?\s+(?P<month>[a-zéûôîà]+)\s+(?P<year>\d{4})",
    re.IGNORECASE,
)


def parse_french_date(text: str | None) -> date | None:
    if not text:
        return None
    m = _FR_DATE_RE.search(text.lower())
    if m is None:
        return None
    month = MOIS_FR.get(m.group("month"))
    if month is None:
        return None
    try:
        return date(int(m.group("year")), month, int(m.group("day")))
    except ValueError:
        return None
