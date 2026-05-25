# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Copyright (c) 2026 Arthur Michon
# See LICENSE for terms; COMMERCIAL_LICENSE.md for commercial use.
"""Discovery adapter for Légifrance JORF search results.

The index page returns a list of arrêtés matching a query. We extract:
- NOR (Numéro d'Ordre de Référence) — the regulator_reference
- the canonical "consult" URL (legifrance.gouv.fr/jorf/id/{NOR})
- publication_date and (when present) effective_date from the result blurb
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, ClassVar
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from application.ports.customs_discovery import (
    DiscoveredPublication,
)
from infrastructure.customs._date_fr import parse_french_date

# NOR pattern: 4 letters + 4-10 digits + 1 letter
# (modern NORs use 10 digits, older arrêtés sometimes use fewer)
_NOR_RE = re.compile(r"\b([A-Z]{4}\d{4,10}[A-Z])\b")


class LegifranceJorfDiscovery:
    name: ClassVar[str] = "legifrance-jorf"

    async def find_publications(
        self,
        *,
        index_html: str,
        index_url: str,
        config: dict[str, Any],
    ) -> Sequence[DiscoveredPublication]:
        tree = HTMLParser(index_html)
        seen: dict[str, DiscoveredPublication] = {}

        # Strategy: collect every NOR mentioned on the page, paired with the
        # closest link to /jorf/id/{NOR}, plus surrounding text for dates.
        # Robust to result-container CSS changes (Légifrance redesigns often).

        # 1. NOR via canonical URLs /jorf/id/<NOR>
        for a in tree.css("a[href*='/jorf/id/']"):
            href = a.attributes.get("href") or ""
            m = _NOR_RE.search(href)
            if not m:
                continue
            nor = m.group(1)
            if nor in seen:
                continue
            absolute = urljoin(index_url, href)
            # The link's text is usually the arrêté title; look up the
            # containing block for the date "du DD mois YYYY".
            # Walk up until the surrounding text exposes a metadata blurb
            # ("applicable …", "à compter du …", "JORF n°…"). The h3
            # alone only has the title — the result-item div has the
            # publication + effective dates as siblings.
            container = a.parent
            blurb_text = ""
            hops = 0
            best_blurb = ""
            keywords = ("applicable", "vigueur", "à compter", "jorf n")
            while container is not None and hops < 6:
                blurb_text = (container.text(separator=" ") or "").strip()
                low = blurb_text.lower()
                if any(kw in low for kw in keywords):
                    best_blurb = blurb_text
                    break
                if len(blurb_text) > len(best_blurb):
                    best_blurb = blurb_text
                container = container.parent
                hops += 1

            pub_date = _extract_publication_date(best_blurb)
            eff_date = _extract_effective_date(best_blurb)

            seen[nor] = DiscoveredPublication(
                regulator_reference=nor,
                document_url=absolute,
                publication_date=pub_date,
                effective_date=eff_date,
                document_mime="text/html",
            )

        # 2. Fallback: NOR mentioned as plain text (some listings render the
        #    NOR before the link). Don't override richer entries.
        for node in tree.css("p, span, div, li"):
            txt = node.text() or ""
            for m in _NOR_RE.finditer(txt):
                nor = m.group(1)
                if nor in seen:
                    continue
                fallback_url = f"https://www.legifrance.gouv.fr/jorf/id/{nor}"
                seen[nor] = DiscoveredPublication(
                    regulator_reference=nor,
                    document_url=fallback_url,
                    publication_date=_extract_publication_date(txt),
                    effective_date=_extract_effective_date(txt),
                    document_mime="text/html",
                )

        return list(seen.values())


# "Arrêté du 4 décembre 2019 portant homologation…"
_DATE_DU_RE = re.compile(r"du\s+(\d{1,2}\s+[a-zéûôîà]+\s+\d{4})", re.IGNORECASE)
# "applicable à compter du 1er janvier 2026", "entre en vigueur le 1er ..."
_EFFECTIVE_RE = re.compile(
    r"(?:applicable|en\s+vigueur|effet|effectives?)"
    r"(?:\s+(?:à\s+compter\s+du|le|au|du))?"
    r"\s+(\d{1,2}(?:er|ᵉʳ)?\s+[a-zéûôîà]+\s+\d{4})",
    re.IGNORECASE,
)


def _extract_publication_date(blurb: str) -> Any:
    m = _DATE_DU_RE.search(blurb)
    return parse_french_date(m.group(1)) if m else None


def _extract_effective_date(blurb: str) -> Any:
    m = _EFFECTIVE_RE.search(blurb)
    return parse_french_date(m.group(1)) if m else None
